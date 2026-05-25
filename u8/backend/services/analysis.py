"""
AnalysisService - Extracts life logs and generates diary summaries from conversation transcripts.
"""
import json
from datetime import datetime, timezone, timedelta

from shared.data_access import (
    DataAccess,
    SK_LIFE_LOG,
    SK_EXPENSE,
    SK_DAILY_FUREMARU_SUMMARY,
    SK_STRESS_SUMMARY,
)
from shared.bedrock_client import BedrockClient


LIFE_LOG_EXTRACTION_SYSTEM = """あなたは会話テキストからユーザーの生活情報を正確に抽出するアシスタントです。
推測や補完はせず、会話に明示的に言及された情報のみをJSON形式で出力してください。"""

LIFE_LOG_EXTRACTION_PROMPT = """以下の会話からユーザーの生活に関する事実を抽出してください。

会話:
{conversation}

以下のJSON配列形式で出力してください（事実がない場合は空配列 [] を返してください）:
[
  {{
    "category": "食事|活動|睡眠|運動|対人|気分|支出|場所|ご褒美",
    "content": "抽出した事実の記述",
    "confidence": 0.5-1.0,
    "timestamp_hint": "午前|午後|夕方|夜|不明",
    "amount": null
  }}
]

注意:
- confidence 0.5未満の不確かな情報は含めない
- category "支出" の場合、amountに金額(整数)を入れる
- 会話に明示されていない情報は絶対に追加しない"""

DIARY_SYSTEM = """あなたは「ふれまーるちゃん」です。
ユーザーの今日一日を振り返る短い日記を書いてください。"""

DIARY_PROMPT = """以下のライフログを元に、ふれまーるちゃん視点の日記を書いてください。

ライフログ:
{life_logs}

支出記録:
{expenses}

【ルール】
- ふれまーるちゃんの視点で「今日の{display_name}は...」と書き始める
- 200-400文字程度
- 温かい言葉で一日を締めくくる
- 明日への一言を添える
- 事実に基づく（推測しない）
- 何もイベントがない場合は「今日はゆっくりだったね」で締める"""

DEFAULT_DIARY = "今日はゆっくりだったね。たまにはこういう日も大事だよ。明日もふれまーるちゃんがそばにいるからね♪"

STRESS_SYSTEM = """あなたは会話テキストからユーザーのストレスレベルを正確に判定するアシスタントです。
推測は控えめにし、会話の内容から読み取れる範囲で判定してください。"""

STRESS_PROMPT = """以下の会話からユーザーのストレスレベルと要因を判定してください。

会話:
{conversation}

以下のJSON形式で出力してください:
{{
  "stress_level": 1-5の整数（1=リラックス、2=やや疲れ、3=ストレスあり、4=かなり高い、5=非常に高い）,
  "factors": ["ストレスの原因1", "原因2"],
  "positive_factors": ["ポジティブな要因1"],
  "mood": "全体的な気分を1語で"
}}

判定基準:
- 明確にネガティブな発言が多い → レベル4-5
- 疲れた・だるいなど軽度 → レベル2-3
- ポジティブな発言が主 → レベル1-2
- 会話が短すぎて判断できない → レベル2（デフォルト）"""


class AnalysisService:
    def __init__(self, da: DataAccess = None, bedrock: BedrockClient = None):
        self.da = da or DataAccess()
        self.bedrock = bedrock or BedrockClient()

    def process_conversation(self, job_id: str, user_id: str, session_id: str) -> None:
        """Process a conversation analysis job: extract life logs and expenses."""
        # Mark job as processing
        self.da.update_item(f"ANALYSIS_JOB#{job_id}", "META#", {
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        try:
            # Get conversation turns for this session
            turns = self.da.query_by_prefix(f"USER#{user_id}", "CONVERSATION_TURN#", limit=500)
            session_turns = [t for t in turns if t.get("session_id") == session_id]

            if not session_turns:
                self.da.update_item(f"ANALYSIS_JOB#{job_id}", "META#", {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "result": "no_turns",
                })
                return

            # Format conversation for LLM
            conversation_text = self._format_conversation(session_turns)

            # Extract life logs
            life_logs = self._extract_life_logs(conversation_text)

            # Save life logs and expenses (日付の境界はJSTで判断)
            jst = timezone(timedelta(hours=9))
            today = datetime.now(jst).strftime("%Y-%m-%d")
            self._save_life_logs(user_id, today, life_logs)

            # Mark job completed
            self.da.update_item(f"ANALYSIS_JOB#{job_id}", "META#", {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "life_log_count": len(life_logs),
            })

        except Exception as e:
            # Mark job as failed
            job = self.da.get_item(f"ANALYSIS_JOB#{job_id}", "META#")
            retry_count = (job or {}).get("retry_count", 0)
            self.da.update_item(f"ANALYSIS_JOB#{job_id}", "META#", {
                "status": "failed",
                "error": str(e)[:500],
                "retry_count": retry_count + 1,
            })
            raise

    def generate_diary_summary(self, user_id: str, date: str = None) -> str:
        """Generate diary summary for a user for the given date."""
        if not date:
            # Use JST today
            jst = timezone(timedelta(hours=9))
            date = datetime.now(jst).strftime("%Y-%m-%d")

        # Get life logs for the date
        life_logs = self.da.query_by_prefix(f"USER#{user_id}", f"LIFE_LOG#{date}")
        expenses = self.da.query_by_prefix(f"USER#{user_id}", f"EXPENSE#")

        # Get user display name
        profile = self.da.get_or_create_profile(user_id)
        display_name = profile.get("display_name", "") or "あなた"

        if not life_logs:
            diary_text = DEFAULT_DIARY
        else:
            # Format for LLM
            logs_text = "\n".join(
                f"- [{log.get('category', '不明')}] {log.get('content', '')}"
                for log in life_logs
            )
            expenses_text = "\n".join(
                f"- {exp.get('description', '不明')}: {exp.get('amount', 0)}円"
                for exp in expenses
                if exp.get("SK", "").startswith(f"EXPENSE#{date}")
            ) or "なし"

            prompt = DIARY_PROMPT.format(
                life_logs=logs_text,
                expenses=expenses_text,
                display_name=display_name,
            )
            diary_text = self.bedrock.invoke(prompt, system=DIARY_SYSTEM, max_tokens=1000, temperature=0.7)

        # Save diary summary
        now = datetime.now(timezone.utc).isoformat()
        sk = SK_DAILY_FUREMARU_SUMMARY.format(date=date)
        self.da.put_item(f"USER#{user_id}", sk, {
            "date": date,
            "content": diary_text,
            "life_log_count": len(life_logs),
            "created_at": now,
            "updated_at": now,
        })

        return diary_text

    def _format_conversation(self, turns: list[dict]) -> str:
        """Format conversation turns into text for LLM."""
        sorted_turns = sorted(turns, key=lambda t: t.get("SK", ""))
        lines = []
        for turn in sorted_turns:
            role = "ユーザー" if turn.get("role") == "user" else "ふれまーるちゃん"
            lines.append(f"{role}: {turn.get('content', '')}")
        return "\n".join(lines)

    def _extract_life_logs(self, conversation_text: str) -> list[dict]:
        """Extract life logs from conversation using Bedrock."""
        prompt = LIFE_LOG_EXTRACTION_PROMPT.format(conversation=conversation_text)
        try:
            result = self.bedrock.invoke_json(prompt, system=LIFE_LOG_EXTRACTION_SYSTEM)
            if not isinstance(result, list):
                return []
            # Filter low confidence
            return [log for log in result if log.get("confidence", 0) >= 0.5]
        except (json.JSONDecodeError, Exception):
            return []

    def _save_life_logs(self, user_id: str, date: str, life_logs: list[dict]) -> None:
        """Save extracted life logs and expenses to DynamoDB."""
        now = datetime.now(timezone.utc).isoformat()

        for seq, log in enumerate(life_logs):
            # Save life log
            sk = SK_LIFE_LOG.format(date=date, seq=str(seq).zfill(3))
            self.da.put_item(f"USER#{user_id}", sk, {
                "category": log.get("category", "不明"),
                "content": log.get("content", ""),
                "confidence": log.get("confidence", 0.5),
                "timestamp_hint": log.get("timestamp_hint", "不明"),
                "created_at": now,
            })

            # If expense, also write EXPENSE#
            if log.get("category") == "支出" and log.get("amount"):
                expense_sk = SK_EXPENSE.format(timestamp=now.replace("+00:00", f".{seq:03d}Z"))
                self.da.put_item(f"USER#{user_id}", expense_sk, {
                    "description": log.get("content", ""),
                    "amount": log["amount"],
                    "source": "voice_analysis",
                    "created_at": now,
                })

    def assess_stress(self, user_id: str, session_id: str) -> dict:
        """Assess stress level from conversation turns."""
        turns = self.da.query_by_prefix(f"USER#{user_id}", "CONVERSATION_TURN#", limit=500)
        session_turns = [t for t in turns if t.get("session_id") == session_id]

        if not session_turns:
            return {"stress_level": 2, "factors": [], "positive_factors": [], "mood": "不明"}

        conversation_text = self._format_conversation(session_turns)
        prompt = STRESS_PROMPT.format(conversation=conversation_text)

        try:
            result = self.bedrock.invoke_json(prompt, system=STRESS_SYSTEM)
        except Exception:
            result = {"stress_level": 2, "factors": [], "positive_factors": [], "mood": "不明"}

        # Clamp stress level
        stress_level = max(1, min(5, int(result.get("stress_level", 2))))
        factors = result.get("factors", [])
        positive_factors = result.get("positive_factors", [])
        mood = result.get("mood", "不明")

        # Save to DynamoDB
        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).isoformat()

        sk = SK_STRESS_SUMMARY.format(date=today)
        self.da.put_item(f"USER#{user_id}", sk, {
            "date": today,
            "stress_level": stress_level,
            "factors": factors,
            "positive_factors": positive_factors,
            "mood": mood,
            "session_id": session_id,
            "created_at": now,
        })

        return {
            "stress_level": stress_level,
            "factors": factors,
            "positive_factors": positive_factors,
            "mood": mood,
        }
