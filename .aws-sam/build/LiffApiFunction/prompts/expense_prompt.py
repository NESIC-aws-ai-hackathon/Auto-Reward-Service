"""
支出抽出プロンプト

ユーザーのテキストから支出情報を JSON で抽出する。
LLM には純粋な JSON のみを返させる（コードブロック・説明文を含まない）。
"""
from __future__ import annotations

# ARS カテゴリ定義（プロンプト用）
_CATEGORY_DESCRIPTION = """
以下の10カテゴリから最も適切なものを1つ選んでください：
- 情緒安定費：プリン・カフェ・スイーツなど日常の小さな癒し
- 回復費：マッサージ・銭湯・映画など意図的なリカバリー
- 緊急回復費：深夜コンビニ爆買いやヤケ食いなど衝動的な出費
- ご褒美費：新しい服・ガジェット・コスメなど自分へのご褒美
- 高級ご褒美費：高級ディナー・ブランド品・スパなど特別な贅沢
- 旅行・体験費：温泉旅行・ホテル・アクティビティなど非日常体験
- 成長投資費：書籍・セミナー・資格・ジムなど自己投資
- おすそわけ費：誕生日プレゼント・記念日ディナーなど他者向けギフト
- 日常消費：食料品・日用品・交通費など生活必需品
- その他：上記に該当しないもの
""".strip()

_SYSTEM_PROMPT = """あなたは支出情報を抽出するアシスタントです。
ユーザーのメッセージから支出情報を抽出して JSON のみを返してください。
説明文やコードブロック（```）は絶対に含めないでください。
必ず純粋な JSON オブジェクトのみを返してください。"""

_OUTPUT_FORMAT = """{
  "is_expense": true または false,
  "items": [
    {
      "item_name": "商品名（不明な場合は null）",
      "amount": 金額の整数（円）（不明な場合は null）,
      "store_name": "店名（不明な場合は null）",
      "category": "カテゴリ名（必須）",
      "confidence": 0.0〜1.0の確信度
    }
  ]
}"""


def build_expense_prompt(text: str) -> str:
    """テキスト支出抽出プロンプトを生成する"""
    # SEC-3-02: 入力長ガード（1,000文字）
    safe_text = text[:1000]
    return f"""ユーザーのメッセージが支出に関するものかどうかを判断し、支出の場合は情報を抽出してください。

【最重要ルール】金額はユーザーが明示的に数字で述べた場合のみ設定してください。
金額の推測・推定・デフォルト値の使用は絶対に禁止です。
例: 「プリン買った」→ amount: null / 「プリン320円」→ amount: 320

ユーザーメッセージ:
{safe_text}

{_CATEGORY_DESCRIPTION}

出力形式（JSON のみ、説明文なし）:
{_OUTPUT_FORMAT}

注意事項:
- 支出メッセージでない場合は is_expense: false とし、items は空配列にしてください
- **金額はユーザーが明示的に述べた場合のみ設定してください。推測・推定は絶対に禁止です。**
  - 例: 「プリン買った」→ amount: null （金額の言及なし）
  - 例: 「プリン320円買った」→ amount: 320
  - 例: 「コーヒー飲んだ」→ amount: null
- 金額の言及がない場合は amount を必ず null にしてください（絶対に推測しないこと）
- 1メッセージに複数の支出が含まれる場合は items に複数含めてください
- 個人名・電話番号・クレジットカード番号は item_name・store_name に含めないでください
- confidence は抽出の確信度（0.0〜1.0）を設定してください"""


def build_clarification_prompt(answer_text: str, partial_items: list[dict]) -> str:
    """追加質問への回答から支出情報を補完するプロンプトを生成する"""
    safe_text = answer_text[:1000]
    partial_info = ""
    if partial_items:
        item = partial_items[0]
        if item.get("item_name"):
            partial_info = f"（商品名: {item['item_name']}）"
    return f"""ユーザーが支出の金額を答えました。金額を抽出して JSON のみを返してください。

{partial_info}
ユーザーの回答: {safe_text}

出力形式（JSON のみ）:
{_OUTPUT_FORMAT}

注意: 金額が読み取れない場合は amount を null にしてください。is_expense は常に true にしてください。"""
