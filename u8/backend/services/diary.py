"""
DiaryService - Retrieves diary summaries and life logs.
Generates diary from LIFE_LOG entries on demand.
"""
import os
from datetime import datetime, timezone, timedelta

import boto3

from shared.data_access import DataAccess, SK_DAILY_FUREMARU_SUMMARY, SK_STRESS_SUMMARY


class DiaryService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()
        self._bedrock = None

    @property
    def bedrock(self):
        if not self._bedrock:
            self._bedrock = boto3.client(
                "bedrock-runtime",
                region_name=os.environ.get("BEDROCK_REGION", "ap-northeast-1"),
            )
        return self._bedrock

    @property
    def model_id(self):
        return os.environ.get(
            "BEDROCK_MODEL_ID",
            "jp.anthropic.claude-haiku-4-5-20251001-v1:0",
        )

    def get_diary_list(self, user_id: str, limit: int = 30) -> dict:
        """Get recent diary entries based on life logs and chat grouped by date."""
        # 1) Daily summaries (cache)
        cached = self.da.query_by_prefix_latest(
            f"USER#{user_id}", "DAILY_FUREMARU_SUMMARY#", limit=limit
        ) or []
        cached_dates = {}
        for c in cached:
            sk = c.get("SK", "")
            date = sk.replace("DAILY_FUREMARU_SUMMARY#", "")[:10]
            if date:
                cached_dates[date] = c.get("content", "")

        # 2) Life logs (fallback for un-summarized days)
        logs = self.da.query_by_prefix_latest(f"USER#{user_id}", "LIFE_LOG#", limit=300) or []
        # 3) Chats also (so days with chat but no lifelog still appear)
        chats = self.da.query_by_prefix_latest(f"USER#{user_id}", "CHAT#", limit=300) or []

        dates_set = set(cached_dates.keys())
        for log in logs:
            d = log.get("date") or (log.get("SK", "")[9:19] if log.get("SK", "").startswith("LIFE_LOG#") else "")
            if d:
                dates_set.add(d)
        for c in chats:
            ts = c.get("user_timestamp") or c.get("timestamp", "")
            if ts:
                dates_set.add(ts[:10])

        sorted_dates = sorted(dates_set, reverse=True)[:limit]

        # group lifelogs and chats by date for counts
        logs_by_date = {}
        for log in logs:
            d = log.get("date") or (log.get("SK", "")[9:19] if log.get("SK", "").startswith("LIFE_LOG#") else "")
            logs_by_date.setdefault(d, []).append(log)
        chats_by_date = {}
        for c in chats:
            ts = c.get("user_timestamp") or c.get("timestamp", "")
            d = ts[:10] if ts else ""
            chats_by_date.setdefault(d, []).append(c)

        entries = []
        for date in sorted_dates:
            content = cached_dates.get(date) or self._summarize_logs(logs_by_date.get(date, []))
            entries.append({
                "date": date,
                "content": content[:200],
                "life_log_count": len(logs_by_date.get(date, [])),
                "chat_count": len(chats_by_date.get(date, [])),
            })

        return {"entries": entries}

    def get_diary_detail(self, user_id: str, date: str) -> dict:
        """Get detailed diary for a specific date. Generates via Bedrock if no cached summary."""
        life_logs = self.da.query_by_prefix(f"USER#{user_id}", f"LIFE_LOG#{date}") or []
        chats = self.da.query_by_prefix(f"USER#{user_id}", f"CHAT#{date}") or []

        sk = SK_DAILY_FUREMARU_SUMMARY.format(date=date)
        diary = self.da.get_item(f"USER#{user_id}", sk)
        content = (diary or {}).get("content", "") if diary else ""

        # 日記コンテンツがなければ Bedrock で生成して保存
        if not content and (life_logs or chats):
            content = self._generate_diary_via_bedrock(date, life_logs, chats)
            if content:
                try:
                    self.da.put_item(
                        f"USER#{user_id}", sk,
                        {
                            "content": content,
                            "date": date,
                            "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
                        },
                    )
                except Exception as e:
                    print(f"diary cache save error: {e}")

        stress_sk = SK_STRESS_SUMMARY.format(date=date)
        stress_item = self.da.get_item(f"USER#{user_id}", stress_sk)
        stress = None
        if stress_item:
            stress = {
                "level": stress_item.get("stress_level"),
                "mood": stress_item.get("mood", ""),
            }

        return {
            "date": date,
            "content": content,
            "life_log_count": len(life_logs),
            "chat_count": len(chats),
            "life_logs": [
                {
                    "category": log.get("category") or log.get("topic", "日常"),
                    "content": log.get("content") or log.get("text", ""),
                    "emotion": log.get("emotion") or log.get("mood", ""),
                    "timestamp": log.get("timestamp", ""),
                }
                for log in life_logs
            ],
            "stress": stress,
        }

    def _generate_diary_via_bedrock(self, date: str, life_logs: list, chats: list) -> str:
        """Bedrock を呼んで日記風サマリを生成する。"""
        try:
            log_lines = []
            for lg in (life_logs or [])[:30]:
                cat = lg.get("category") or lg.get("topic") or ""
                cnt = lg.get("content") or lg.get("text") or ""
                emo = lg.get("emotion") or lg.get("mood") or ""
                if cnt:
                    log_lines.append(f"・[{cat}/{emo}] {cnt}")
            chat_lines = []
            for c in (chats or [])[:40]:
                u = c.get("user_message") or ""
                a = c.get("assistant_message") or ""
                if u:
                    chat_lines.append(f"私: {u}")
                if a:
                    chat_lines.append(f"ふれまーる: {a}")

            material = "\n".join(log_lines + chat_lines)[:4000]
            if not material.strip():
                return ""

            system = (
                "あなたは『ふれまーるちゃん』という女の子AIアシスタントです。"
                "ユーザーがその日に話した内容を元に、本人視点の日記を書いてください。"
                "口調はゆるく親しみやすく、150〜250文字程度で。"
                "前向きに締めくくり、責めたり否定したりしない。語尾に♪や〜を時々入れる。"
            )
            user_prompt = (
                f"以下は {date} の会話とライフログの抜粋です。これをもとに、その日の日記を書いてください。\n\n"
                f"{material}"
            )

            resp = self.bedrock.converse(
                modelId=self.model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                inferenceConfig={"maxTokens": 500, "temperature": 0.8},
            )
            out = resp.get("output", {}).get("message", {}).get("content", [])
            for blk in out:
                if "text" in blk:
                    return blk["text"].strip()
        except Exception as e:
            print(f"diary bedrock error: {e}")
        return ""

    def _summarize_logs(self, logs: list) -> str:
        if not logs:
            return ""
        parts = []
        for log in logs[:6]:
            content = log.get("content") or log.get("text", "")
            category = log.get("category") or log.get("topic", "")
            if content:
                if category and category != "日常":
                    parts.append(f"[{category}] {content}")
                else:
                    parts.append(content)
        return " / ".join(parts) if parts else ""
