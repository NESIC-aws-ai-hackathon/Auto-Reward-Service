"""
ReceiptService - Extract expense data from receipt images using multimodal AI.
Uses Claude Haiku 4.5 (vision-capable) to parse receipt images.
"""
import json
import os
import base64
import traceback
from datetime import datetime, timezone

import boto3

from shared.data_access import DataAccess
from shared.config import get_config


class ReceiptService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()
        self.config = get_config()
        self._bedrock = None

    @property
    def bedrock(self):
        if not self._bedrock:
            region = os.environ.get("BEDROCK_REGION", "ap-northeast-1")
            self._bedrock = boto3.client("bedrock-runtime", region_name=region)
        return self._bedrock

    @property
    def model_id(self):
        return os.environ.get("BEDROCK_MODEL_ID", "jp.anthropic.claude-haiku-4-5-20251001-v1:0")

    def process_receipt(self, user_id: str, image_base64: str, media_type: str = "image/jpeg",
                        user_note: str = "") -> dict:
        """
        Process a receipt image and extract expense data.
        Returns: {items: [...], total: int, store: str, date: str, reply: str}
        """
        now = datetime.now(timezone.utc).isoformat()

        # Call multimodal AI to parse receipt
        extracted = self._extract_from_image(image_base64, media_type, user_note)

        if not extracted or not extracted.get("items"):
            return {
                "success": False,
                "reply": "ごめんね、レシートがうまく読み取れなかった……。もう一度写真を撮ってみてくれる？♪",
                "items": [],
            }

        # Save each expense item
        saved_items = []
        total_amount = 0
        for item in extracted["items"]:
            item_name = item.get("name", "不明")
            amount = int(item.get("amount", 0))
            if amount <= 0:
                continue

            from services.chat_service import ChatService
            svc = ChatService(self.da)
            category = svc._categorize_expense(item_name)

            expense_time = datetime.now(timezone.utc).isoformat()
            self.da.put_item(f"USER#{user_id}", f"EXPENSE#{expense_time}", {
                "item": item_name,
                "amount": amount,
                "ars_category": category,
                "source": "receipt",
                "store": extracted.get("store", ""),
                "receipt_date": extracted.get("date", ""),
                "confirmed_at": now,
                "timestamp": expense_time,
            })
            saved_items.append({"item": item_name, "amount": amount, "category": category})
            total_amount += amount

        # Update monthly summary
        if total_amount > 0:
            from services.chat_service import ChatService
            svc = ChatService(self.da)
            svc._update_monthly_summary(user_id, total_amount, now)

        # Generate reply
        store = extracted.get("store", "")
        item_count = len(saved_items)
        store_text = f"「{store}」で" if store else ""
        reply = f"{store_text}{item_count}品、合計{total_amount}円を記録したよ♪ おつかれさま〜！"

        return {
            "success": True,
            "reply": reply,
            "items": saved_items,
            "total": total_amount,
            "store": store,
            "date": extracted.get("date", ""),
        }

    def _extract_from_image(self, image_base64: str, media_type: str,
                            user_note: str = "") -> dict | None:
        """Use Claude Haiku 4.5 vision to extract receipt data."""
        prompt = """このレシート画像から以下の情報をJSON形式で抽出してください。

出力形式:
{
  "store": "店名",
  "date": "YYYY-MM-DD（読み取れない場合は空文字）",
  "items": [
    {"name": "商品名", "amount": 金額（整数）},
    ...
  ],
  "total": 合計金額（整数）
}

注意:
- 金額は税込みの数値で。小数点以下は四捨五入
- 商品名は簡潔に（長い場合は要約）
- 読み取れない部分は推測せず省略
- 値引き・割引は別項目にせず、最終金額を使用
- JSONのみ出力（説明文不要）"""

        if user_note:
            prompt += f"\n\nユーザーからの補足: {user_note}"

        messages = [{
            "role": "user",
            "content": [
                {
                    "image": {
                        "format": media_type.split("/")[-1] if "/" in media_type else "jpeg",
                        "source": {"bytes": base64.b64decode(image_base64)},
                    }
                },
                {"text": prompt},
            ],
        }]

        try:
            resp = self.bedrock.converse(
                modelId=self.model_id,
                messages=messages,
                inferenceConfig={"maxTokens": 1000, "temperature": 0.1},
            )
            text = resp["output"]["message"]["content"][0]["text"]

            # Extract JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            print(f"Receipt extraction error: {e}")
            traceback.print_exc()

        return None
