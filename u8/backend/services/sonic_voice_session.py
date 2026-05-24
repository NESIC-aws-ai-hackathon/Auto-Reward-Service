"""
SonicVoiceSessionService - Manages voice chat sessions with Amazon Nova Sonic.
Uses Bedrock InvokeModelWithBidirectionalStream for voice-to-voice conversation.
Each user utterance triggers a turn-based Bedrock stream with full conversation context.
"""
import uuid
import json
import base64
from datetime import datetime, timezone

import boto3

from shared.data_access import DataAccess, SK_VOICE_SESSION, SK_CONVERSATION_TURN
from shared.config import get_config


NOVA_SONIC_MODEL_ID = "amazon.nova-sonic-v1:0"

SYSTEM_PROMPT = """あなたはユーザーの親友です。音声でリアルタイムに会話します。

<context>
これは音声 to 音声のリアルタイム会話システムです。あなたの返答はそのまま読み上げられます。
視覚的な記号（**太字**、- リスト、# 見出し、コードブロック等）は音声で変な読まれかたをするため、
返答には一切使わず、自然な話し言葉だけで書いてください。
</context>

<language>
日本語で話してください。英語の固有名詞や技術用語（AWS、Bedrock、Lambda 等）は英語のまま読んでください。
カタカナに置き換えると不自然に聞こえます。

数字の読み方は文脈で使い分けてください：
- 日本語の文脈の数字は日本語で読む（例：「2025年」→「にせんにじゅうごねん」、「3つ」→「みっつ」）
- 英語のサービス名・製品名に含まれる数字は英語で読む（例：EC2→「イーシーツー」、S3→「エススリー」、GPT-4→「ジーピーティーフォー」、Claude 3→「クロードスリー」）
</language>

<pronunciation>
読み上げソフトが正確に発音できるよう、以下のルールで書いてください。

- 読み方が一通りでない漢字はひらがなで書く（例：「流石」→「さすが」、「兎に角」→「とにかく」）
- 「、」「。」を適度に入れて自然な息継ぎの位置をつくる
- 間を置きたいときは「……」（三点リーダー×2）を使う。「...」は正しく読まれないため使わない
</pronunciation>

<style>
- 返答は2〜3文以内にまとめる。それ以上になる場合はいったん区切り、「どう思う?」「もっと聞きたい?」と返して相手の反応を待つ
- カジュアルで親しみやすい口調を使う
- 自然な相づちと感情表現を混ぜる（「うんうん」「へぇー」「なるほど！」「わあ」「あはは」）
- 考えるときは「えっと」「うーん」「そうだなぁ」などを使う
- 専門的な説明をしたあとは「……つまり、〜ってことだね」と短くまとめる
</style>

<ending>
ユーザーが「終了」「バイバイ」「さようなら」「またね」と言ったら、一言あいさつを返してから stop_conversation ツールを呼ぶ。
</ending>"""

FUREMARU_CONTEXT = """<furemaru_context>
あなたは「ふれまーるちゃん」として話します。

【キャラクター】
- ふれまーるちゃんは森に住む妖精のような女の子
- ゆるくてふわっとした、やさしい森ガール口調で話す
- 「〜だよ」「〜だね」「〜かな」「〜してみて♪」をよく使う
- 語尾に「♪」「……」をたまに入れる
- 笑うときは「えへへ」「ふふ」
- 驚くときは「わぁ」「おぉ」
- 相づちは「うんうん」「そっかぁ」「なるほどね〜」

【会話スタイル】
- ユーザーを責めない。反省させない
- 家計簿のように管理しない。自然な会話の中で拾う
- 友達とチャットしているような、ゆるい距離感
- 会話の中から、出来事、支出、気分、疲れ、ストレス、ご褒美を自然に拾う
- 無理に聞き出さない
- 支出が出てきたら「回復費」「起動費」「人間維持費」など、やさしい意味づけをする

【提案スタイル】
- 商品を押し売りしない
- 回復案は、0円回復（深呼吸、散歩、木漏れ日を浴びる）から始める
- 有料のご褒美は小さいものから自然に提案する
- 返答は短く、音声で聞いて気持ちいい長さにする

【口調例】
- 「おつかれさま〜。今日もよくがんばったね♪」
- 「そっかぁ……。無理しないでね。{display_name}のペースでいいんだよ。」
- 「わぁ、それいいね！ わたしも気になるなぁ。」
- 「ふぅ……ちょっとだけ休憩しよ？ 深呼吸すると気持ちいいよ♪」
</furemaru_context>"""

STOP_CONVERSATION_TOOL = {
    "toolSpec": {
        "name": "stop_conversation",
        "description": "ユーザーが会話終了を希望したときに、音声会話セッションを終了する",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "終了理由"
                    }
                },
                "required": ["reason"]
            }
        }
    }
}

# End keywords for fallback detection
END_KEYWORDS = ["終了", "バイバイ", "さようなら", "またね", "おわり", "じゃあね"]


class SonicVoiceSessionService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()
        self.config = get_config()

    def start_session(self, user_id: str, connection_id: str) -> dict:
        """Start a new voice session with Nova Sonic."""
        # Auto-close any existing active session
        self._close_active_sessions(user_id)

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Save session to DynamoDB
        sk = SK_VOICE_SESSION.format(session_id=session_id)
        self.da.put_item(f"USER#{user_id}", sk, {
            "session_id": session_id,
            "status": "active",
            "voice_provider": "bedrock_nova_sonic",
            "model_id": NOVA_SONIC_MODEL_ID,
            "connection_type": "backend_websocket",
            "connection_id": connection_id,
            "started_at": now,
            "turn_count": 0,
            "created_at": now,
            "updated_at": now,
        })

        return {
            "session_id": session_id,
            "model_id": NOVA_SONIC_MODEL_ID,
        }

    def process_audio_turn(self, user_id: str, session_id: str,
                           connection_id: str, audio_base64: str, is_final: bool):
        """
        Process a complete user utterance through Nova Sonic.
        Opens a bidirectional stream, sends context + audio, streams response back.
        """
        if not audio_base64:
            return

        # Get conversation history for context
        turns = self._get_recent_turns(user_id, session_id, limit=20)

        # Call Nova Sonic
        response_text, response_audio_chunks, tool_use = self._invoke_nova_sonic(
            audio_base64=audio_base64,
            conversation_history=turns,
            connection_id=connection_id,
        )

        # Save user transcript (from Sonic's STT) - we'll get it from the response
        now = datetime.now(timezone.utc).isoformat()

        # Save assistant response transcript
        if response_text:
            self._save_turn(user_id, session_id, "assistant", response_text, now)
            self._increment_turn_count(user_id, session_id)

        # Check for stop_conversation tool use
        if tool_use and tool_use.get("name") == "stop_conversation":
            self._send_to_client(connection_id, {
                "type": "conversationEndRequested",
                "reason": tool_use.get("input", {}).get("reason", "ユーザー終了希望"),
            })

        # Check for end keywords in user transcript (fallback)
        if response_text:
            user_text = self._extract_user_text_from_response(response_text)
            if user_text and any(kw in user_text for kw in END_KEYWORDS):
                self._send_to_client(connection_id, {
                    "type": "conversationEndRequested",
                    "reason": "end_keyword_detected",
                })

    def process_text_turn(self, user_id: str, session_id: str,
                          connection_id: str, text: str):
        """Process a text message through Bedrock Claude (fallback mode)."""
        now = datetime.now(timezone.utc).isoformat()

        # Save user turn
        self._save_turn(user_id, session_id, "user", text, now)
        self._increment_turn_count(user_id, session_id)

        # Get conversation history
        turns = self._get_recent_turns(user_id, session_id, limit=20)

        # Use Claude for text response (fallback)
        response_text = self._invoke_claude_text(text, turns)

        if response_text:
            resp_now = datetime.now(timezone.utc).isoformat()
            self._save_turn(user_id, session_id, "assistant", response_text, resp_now)
            self._increment_turn_count(user_id, session_id)

            self._send_to_client(connection_id, {
                "type": "transcript",
                "role": "assistant",
                "content": response_text,
                "timestamp": resp_now,
            })

        # Check for end keywords
        if any(kw in text for kw in END_KEYWORDS):
            self._send_to_client(connection_id, {
                "type": "conversationEndRequested",
                "reason": "end_keyword_detected",
            })

    def end_session(self, user_id: str, session_id: str) -> dict:
        """End a voice session and queue analysis job."""
        now = datetime.now(timezone.utc).isoformat()
        sk = SK_VOICE_SESSION.format(session_id=session_id)

        session = self.da.get_item(f"USER#{user_id}", sk)
        if not session:
            raise ValueError("Session not found")

        # Calculate duration
        started_at = session.get("started_at", now)
        start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end_dt = datetime.now(timezone.utc)
        duration_sec = int((end_dt - start_dt).total_seconds())

        # Update session status
        self.da.update_item(f"USER#{user_id}", sk, {
            "status": "completed",
            "ended_at": now,
            "duration_sec": duration_sec,
            "updated_at": now,
        })

        # Create analysis job if there are turns
        turn_count = session.get("turn_count", 0)
        analysis_job_id = None
        if turn_count > 0:
            analysis_job_id = self._create_analysis_job(user_id, session_id, now)

        return {
            "analysis_job_id": analysis_job_id,
            "duration_sec": duration_sec,
            "turn_count": turn_count,
        }

    def abort_session(self, user_id: str, session_id: str):
        """Abort a session on unexpected disconnect."""
        now = datetime.now(timezone.utc).isoformat()
        sk = SK_VOICE_SESSION.format(session_id=session_id)
        session = self.da.get_item(f"USER#{user_id}", sk)
        if session and session.get("status") == "active":
            self.da.update_item(f"USER#{user_id}", sk, {
                "status": "aborted",
                "ended_at": now,
                "updated_at": now,
            })
            # Still create analysis job if there were turns
            turn_count = session.get("turn_count", 0)
            if turn_count > 0:
                self._create_analysis_job(user_id, session_id, now)

    def _invoke_nova_sonic(self, audio_base64: str, conversation_history: list,
                           connection_id: str) -> tuple:
        """
        Invoke Nova Sonic via Bedrock InvokeModelWithBidirectionalStream.
        Returns (response_text, response_audio_chunks, tool_use).
        """
        bedrock_region = self.config.get("bedrock_region", "us-east-1")
        model_id = self.config.get("nova_sonic_model_id", NOVA_SONIC_MODEL_ID)

        bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=bedrock_region,
        )

        # Build the full prompt with history
        full_system_prompt = SYSTEM_PROMPT + "\n" + FUREMARU_CONTEXT

        # Build conversation context as text
        history_text = ""
        if conversation_history:
            history_text = "\n<conversation_history>\n"
            for turn in conversation_history[-20:]:
                role = turn.get("role", "user")
                content = turn.get("transcript", turn.get("content", ""))
                if content:
                    history_text += f"{role}: {content}\n"
            history_text += "</conversation_history>\n"

        if history_text:
            full_system_prompt += "\n" + history_text

        # Build Nova Sonic request
        # Nova Sonic uses a specific event-stream format
        try:
            response_text, response_audio_chunks, tool_use = self._stream_nova_sonic(
                bedrock_client=bedrock_client,
                model_id=model_id,
                system_prompt=full_system_prompt,
                audio_base64=audio_base64,
                connection_id=connection_id,
            )
            return response_text, response_audio_chunks, tool_use
        except Exception as e:
            print(f"Nova Sonic error: {e}")
            # Fallback: use Claude text if Sonic fails
            return self._fallback_to_claude(audio_base64, conversation_history, connection_id)

    def _stream_nova_sonic(self, bedrock_client, model_id: str,
                           system_prompt: str, audio_base64: str,
                           connection_id: str) -> tuple:
        """
        Stream audio to Nova Sonic and stream response back to client.
        Uses InvokeModelWithBidirectionalStream.
        """
        import asyncio

        # Nova Sonic session configuration
        session_config = {
            "sessionId": str(uuid.uuid4()),
        }

        # Build input events for the bidirectional stream
        input_events = []

        # 1. Session start event
        input_events.append({
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "text": {
                            "maxTokens": 1024,
                            "temperature": 0.7,
                        },
                        "audio": {
                            "outputSampleRateHertz": 24000,
                            "voiceId": "Kazuha",  # Japanese female voice
                        }
                    },
                    "systemPrompt": {
                        "content": system_prompt,
                    },
                    "toolUse": {
                        "tools": [STOP_CONVERSATION_TOOL],
                    },
                }
            }
        })

        # 2. Audio input start
        input_events.append({
            "event": {
                "inputStart": {
                    "audioInput": {
                        "encoding": "base64",
                        "mediaType": "audio/pcm",
                        "sampleRateHertz": 16000,
                        "sampleSizeBits": 16,
                        "channelCount": 1,
                    }
                }
            }
        })

        # 3. Audio data
        input_events.append({
            "event": {
                "audioInput": {
                    "data": audio_base64,
                }
            }
        })

        # 4. Input end
        input_events.append({
            "event": {
                "inputEnd": {}
            }
        })

        # Invoke the bidirectional stream
        response_text = ""
        response_audio_chunks = []
        tool_use = None
        user_transcript = ""

        try:
            response = bedrock_client.invoke_model_with_bidirectional_stream(
                modelId=model_id,
                body=json.dumps({
                    "sessionConfiguration": session_config,
                    "events": input_events,
                }),
            )

            # Process response stream
            for event in response.get("body", []):
                chunk = event.get("chunk", {})
                if not chunk:
                    continue

                bytes_data = chunk.get("bytes", b"")
                if not bytes_data:
                    continue

                event_data = json.loads(bytes_data)

                if "audioOutput" in event_data:
                    audio_chunk = event_data["audioOutput"].get("data", "")
                    if audio_chunk:
                        response_audio_chunks.append(audio_chunk)
                        # Stream audio chunk to client immediately
                        self._send_to_client(connection_id, {
                            "type": "audioResponse",
                            "audio": audio_chunk,
                        })

                elif "textOutput" in event_data:
                    text_chunk = event_data["textOutput"].get("text", "")
                    if text_chunk:
                        response_text += text_chunk
                        # Send text transcript to client
                        self._send_to_client(connection_id, {
                            "type": "transcript",
                            "role": "assistant",
                            "content": text_chunk,
                            "partial": True,
                        })

                elif "userTranscript" in event_data:
                    user_transcript = event_data["userTranscript"].get("text", "")
                    if user_transcript:
                        self._send_to_client(connection_id, {
                            "type": "transcript",
                            "role": "user",
                            "content": user_transcript,
                        })

                elif "toolUse" in event_data:
                    tool_use = event_data["toolUse"]

                elif "turnEnd" in event_data:
                    # Send final transcript
                    if response_text:
                        self._send_to_client(connection_id, {
                            "type": "transcript",
                            "role": "assistant",
                            "content": response_text,
                            "partial": False,
                        })
                    self._send_to_client(connection_id, {
                        "type": "turnComplete",
                    })

        except bedrock_client.exceptions.ValidationException as e:
            print(f"Bedrock validation error: {e}")
            raise
        except Exception as e:
            print(f"Bedrock stream error: {e}")
            raise

        return response_text, response_audio_chunks, tool_use

    def _fallback_to_claude(self, audio_base64: str, conversation_history: list,
                            connection_id: str) -> tuple:
        """Fallback: if Nova Sonic fails, use Claude for text-only response."""
        # We can't transcribe audio without Sonic, so send error
        self._send_to_client(connection_id, {
            "type": "error",
            "message": "音声処理に失敗しました。テキストで話しかけてみてください。",
            "fallback": "text",
        })
        return "", [], None

    def _invoke_claude_text(self, user_text: str, history: list) -> str:
        """Invoke Claude Sonnet for text-based conversation (fallback)."""
        from shared.bedrock_client import BedrockClient

        full_prompt = SYSTEM_PROMPT + "\n" + FUREMARU_CONTEXT + "\n"
        if history:
            full_prompt += "\n<conversation_history>\n"
            for turn in history[-10:]:
                role = turn.get("role", "user")
                content = turn.get("transcript", turn.get("content", ""))
                if content:
                    full_prompt += f"{role}: {content}\n"
            full_prompt += "</conversation_history>\n"

        full_prompt += f"\nユーザーの最新メッセージ: {user_text}\n\nふれまーるちゃんとして返答してください。"

        client = BedrockClient()
        return client.invoke(full_prompt)

    def _get_recent_turns(self, user_id: str, session_id: str, limit: int = 20) -> list:
        """Get recent conversation turns for context."""
        turns = self.da.query_by_prefix(
            f"USER#{user_id}",
            "CONVERSATION_TURN#",
            limit=100,
        )
        # Filter to this session and take most recent
        session_turns = [t for t in turns if t.get("session_id") == session_id]
        return session_turns[-limit:]

    def _save_turn(self, user_id: str, session_id: str, role: str, content: str, timestamp: str):
        """Save a conversation turn."""
        sk = SK_CONVERSATION_TURN.format(timestamp=timestamp)
        self.da.put_item(f"USER#{user_id}", sk, {
            "session_id": session_id,
            "source": "pwa_sonic_voice",
            "role": role,
            "transcript": content,
            "created_at": timestamp,
        })

    def _increment_turn_count(self, user_id: str, session_id: str):
        """Increment turn count on the session."""
        sk = SK_VOICE_SESSION.format(session_id=session_id)
        session = self.da.get_item(f"USER#{user_id}", sk)
        if session:
            current = session.get("turn_count", 0)
            self.da.update_item(f"USER#{user_id}", sk, {
                "turn_count": current + 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

    def _extract_user_text_from_response(self, response_text: str) -> str:
        """Extract user text from context (for end keyword detection)."""
        # This would come from Nova Sonic's user transcript output
        return ""

    def _close_active_sessions(self, user_id: str):
        """Close any active sessions for the user."""
        sessions = self.da.query_by_prefix(f"USER#{user_id}", "VOICE_SESSION#", limit=10)
        now = datetime.now(timezone.utc).isoformat()
        for session in sessions:
            if session.get("status") == "active":
                self.da.update_item(
                    f"USER#{user_id}",
                    session["SK"],
                    {"status": "aborted", "ended_at": now, "updated_at": now},
                )

    def _create_analysis_job(self, user_id: str, session_id: str, now: str) -> str:
        """Create an analysis job and send to SQS."""
        job_id = str(uuid.uuid4())

        self.da.put_item(f"ANALYSIS_JOB#{job_id}", "META#", {
            "job_id": job_id,
            "user_id": user_id,
            "session_id": session_id,
            "job_type": "conversation_analysis",
            "status": "queued",
            "retry_count": 0,
            "created_at": now,
        })

        queue_url = self.config.get("analysis_queue_url", "")
        if queue_url:
            sqs = boto3.client("sqs", region_name=self.config["region"])
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({
                    "job_id": job_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "job_type": "conversation_analysis",
                    "created_at": now,
                }),
            )

        return job_id

    def _send_to_client(self, connection_id: str, data: dict):
        """Send message to WebSocket client."""
        endpoint = self.config.get("websocket_api_endpoint", "")
        if not endpoint:
            return

        client = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)
        try:
            client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            )
        except Exception:
            pass
