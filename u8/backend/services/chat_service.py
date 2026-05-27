"""
ChatService - メッセージ処理オーケストレーター。
intent 分類 / 支出抽出 / ライフログ蓄積 / 自然な提案を担当する。
"""
import json
import os
import re
import random
import traceback
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3

from shared.data_access import DataAccess
from shared.config import get_config


JST = timezone(timedelta(hours=9))


def _now_jst_iso() -> str:
    """JST タイムゾーン付きの現在時刻 ISO 文字列を返す。"""
    return datetime.now(JST).isoformat()


# ─── Constants ───
INTENT_EXPENSE = "EXPENSE"
INTENT_REWARD = "REWARD"
INTENT_GREET = "GREET"
INTENT_CHAT = "CHAT"
INTENT_CONFIRM_YES = "CONFIRM_YES"
INTENT_CONFIRM_NO = "CONFIRM_NO"
INTENT_UNKNOWN = "UNKNOWN"

ARS_CATEGORIES = {
    "recovery": "回復費",
    "startup": "起動費",
    "maintenance": "維持費",
    "investment": "自己投資",
    "social": "つながり費",
    "other": "その他",
}


class ChatService:
    REWARD_HINT_WORDS = (
        "疲", "つかれ", "しんど", "癒", "休", "ごほうび", "ご褒美",
        "リフレ", "ストレス", "頑張った", "がんばった", "ぐったり", "へとへと",
    )

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
        return os.environ.get(
            "BEDROCK_MODEL_ID",
            "jp.anthropic.claude-haiku-4-5-20251001-v1:0",
        )

    # ─── public ───

    def process_message(self, user_id: str, content: str) -> dict:
        now = _now_jst_iso()
        profile = self.da.get_or_create_profile(user_id) or {}
        display_name = profile.get("display_name", "") or "あなた"

        intent, intent_data = self._classify_intent(content)

        if intent == INTENT_EXPENSE:
            result = self._handle_expense_intent(user_id, content, intent_data, profile, now)
        else:
            result = self._handle_chat_intent(user_id, content, profile, display_name, now, intent)

        # ライフログとして副次情報を抽出
        try:
            self._extract_side_effects(user_id, content, intent, now)
        except Exception as e:
            print(f"side_effects skip: {e}")

        # ユーザーの興味を学習
        try:
            self._update_user_interests(user_id, content, intent)
        except Exception as e:
            print(f"interests update skip: {e}")

        # 会話履歴を保存
        saved_ts = self._save_turn(user_id, now, content, result["reply"], intent)
        result["user_timestamp"] = now
        result["reply_timestamp"] = saved_ts
        result.setdefault("intent", intent)

        # たまにそっと提案
        try:
            suggestion = self._maybe_build_suggestion(user_id, content, intent, result, profile)
            if suggestion:
                result["suggestion"] = suggestion
        except Exception as e:
            print(f"suggestion skip: {e}")

        return result

    # ─── intent classification ───

    _AMOUNT_RE = re.compile(r"(\d{1,7})\s*円")

    def _classify_intent(self, content: str) -> tuple[str, dict]:
        """シンプルなルールベース intent 分類。"""
        text = (content or "").strip()
        if not text:
            return INTENT_UNKNOWN, {}

        # YES/NO 確認
        if re.fullmatch(r"\s*(はい|うん|YES|yes|Yes|y|Y|そう|お願い|おk|OK|ok)\s*[。!！.\s]*", text):
            return INTENT_CONFIRM_YES, {}
        if re.fullmatch(r"\s*(いいえ|いや|NO|no|No|n|N|やめ|やめて|ちがう|違う)\s*[。!！.\s]*", text):
            return INTENT_CONFIRM_NO, {}

        # 金額表現を含む → 支出
        m = self._AMOUNT_RE.search(text)
        if m:
            amount = int(m.group(1))
            # 商品名を雑に抽出(数字より前の最初の名詞っぽい塊)
            head = text[: m.start()].strip()
            head = re.sub(r"(を|で|に|が|は|、|，|,|。)$", "", head).strip()
            item = head or "買い物"
            return INTENT_EXPENSE, {"item": item, "amount": amount}

        # ご褒美ワード
        if any(w in text for w in self.REWARD_HINT_WORDS):
            return INTENT_REWARD, {}

        return INTENT_CHAT, {}

    # ─── expense ───

    def _handle_expense_intent(self, user_id, content, intent_data, profile, now):
        item = intent_data.get("item", "買い物")
        amount = int(intent_data.get("amount", 0))
        category = self._categorize_expense(item)
        category_label = ARS_CATEGORIES.get(category, "その他")
        excuse_tag = self._generate_excuse_tag(item, amount, category)

        self._save_expense(user_id, item, amount, now, category=category, excuse_tag=excuse_tag)
        self._update_monthly_summary(user_id, amount, now)

        # 残予算メッセージ
        budget_msg = ""
        try:
            surplus = int(profile.get("monthly_surplus", 0) or 0)
            if surplus:
                ym = now[:7]
                ms = self.da.get_item(f"USER#{user_id}", f"MONTHLY_SUMMARY#{ym}")
                spent = int(ms.get("total_spent", 0)) if ms else 0
                remaining = max(0, surplus - spent)
                budget_msg = f"\n今月のお小遣い、あと {remaining:,} 円だよ"
        except Exception:
            pass

        templates = [
            f"「{item}」{amount}円、記録したよ。今日の{category_label}だね「{excuse_tag}」{budget_msg}",
            f"{item}に{amount}円ね、{category_label}として覚えておくね♪{budget_msg}",
            f"了解〜！{item} {amount}円、{category_label}に入れとくよ♪{budget_msg}",
        ]
        reply = random.choice(templates)

        return {
            "reply": reply,
            "intent": INTENT_EXPENSE,
            "expense_saved": True,
            "expense": {
                "item": item,
                "amount": amount,
                "category": category,
                "category_label": category_label,
                "excuse_tag": excuse_tag,
            },
        }

    def _save_expense(self, user_id, item, amount, now, category=None, excuse_tag=None, source="chat"):
        category = category or self._categorize_expense(item)
        excuse_tag = excuse_tag or self._generate_excuse_tag(item, amount, category)
        self.da.put_item(
            f"USER#{user_id}",
            f"EXPENSE#{now}",
            {
                "item": item,
                "amount": Decimal(str(amount)),
                "ars_category": category,
                "ars_category_label": ARS_CATEGORIES.get(category, "その他"),
                "excuse_tag": excuse_tag,
                "source": source,
                "timestamp": now,
                "date": now[:10],
            },
        )

    def _update_monthly_summary(self, user_id, amount, now):
        ym = now[:7]
        sk = f"MONTHLY_SUMMARY#{ym}"
        existing = self.da.get_item(f"USER#{user_id}", sk) or {}
        total = int(existing.get("total_spent", 0)) + int(amount)
        count = int(existing.get("count", 0)) + 1
        self.da.put_item(
            f"USER#{user_id}", sk,
            {
                "total_spent": Decimal(str(total)),
                "count": Decimal(str(count)),
                "month": ym,
                "updated_at": now,
            },
        )

    def _categorize_expense(self, item: str) -> str:
        text = (item or "").lower()
        rules = [
            ("recovery", ["コーヒー", "カフェ", "スタバ", "ドリンク", "甘", "スイーツ", "ケーキ",
                          "チョコ", "アイス", "お菓子", "ジュース", "茶", "コンビニ", "弁当",
                          "マッサージ", "風呂", "湯", "サウナ", "癒"]),
            ("startup", ["朝食", "モーニング", "栄養", "ドリンク剤", "サプリ", "プロテイン",
                        "ガソリン", "電車", "バス", "タクシー", "交通", "通勤"]),
            ("social", ["飲み", "ランチ", "ディナー", "外食", "居酒屋", "プレゼント", "贈",
                       "ギフト", "おごり", "おみやげ"]),
            ("investment", ["本", "書籍", "セミナー", "受講", "教材", "学", "ジム", "運動",
                           "ヨガ", "資格", "オンライン"]),
            ("maintenance", ["家賃", "光熱", "電気", "ガス", "水道", "通信", "保険", "薬",
                            "病院", "クリニック", "歯医者", "日用品", "洗剤", "ティッシュ"]),
        ]
        for cat, words in rules:
            for w in words:
                if w.lower() in text:
                    return cat
        return "other"

    def _generate_excuse_tag(self, item: str, amount: int, category: str) -> str:
        cat_tags = {
            "recovery": ["今日もよく頑張ったから", "心の回復タイム", "ちょっと自分を労る", "ご褒美時間"],
            "startup": ["1日のスタートに必要", "気合いを入れる投資", "良い1日のために"],
            "maintenance": ["生活に必要", "ちゃんと整える", "暮らしを支えるやつ"],
            "investment": ["未来の自分への投資", "成長のためのコスト", "学びは資産"],
            "social": ["大事な人との時間", "つながりを大切に", "誰かと笑うための支出"],
            "other": ["まあいっか、ちょっとだけ", "今日はこれくらい許して"],
        }
        return random.choice(cat_tags.get(category, cat_tags["other"]))

    # ─── chat (Bedrock) ───

    def _handle_chat_intent(self, user_id, content, profile, display_name, now, intent):
        reply = self._generate_reply_with_context(user_id, content, profile, display_name, now)
        return {"reply": reply, "intent": intent}

    def _generate_reply_with_context(self, user_id, content, profile, display_name, now) -> str:
        # コンテキスト構築
        context_parts = []

        # 月次サマリ
        try:
            ym = now[:7]
            ms = self.da.get_item(f"USER#{user_id}", f"MONTHLY_SUMMARY#{ym}")
            spent = int(ms.get("total_spent", 0)) if ms else 0
            surplus = int(profile.get("monthly_surplus", 0) or 0)
            if surplus:
                remaining = max(0, surplus - spent)
                context_parts.append(f"今月の支出: {spent:,}円 / お小遣い: {surplus:,}円 / 残り: {remaining:,}円")
            elif spent:
                context_parts.append(f"今月の支出合計: {spent:,}円")
        except Exception:
            pass

        # ライフログ(直近のユーザー属性) → ふれまーるちゃんがユーザーの趣味・性格を理解する
        try:
            lifelogs = self.da.query_by_prefix_latest(f"USER#{user_id}", "LIFE_LOG#", limit=40)
            if lifelogs:
                topics, moods, hobbies = [], [], []
                for lg in lifelogs:
                    t = lg.get("topic") or lg.get("category") or ""
                    if t and t not in topics and t != "日常":
                        topics.append(t)
                    m = lg.get("emotion") or lg.get("mood")
                    if m and m not in ("neutral", "") and m not in moods:
                        moods.append(m)
                    c = (lg.get("content") or lg.get("text") or "").strip()
                    if c and len(c) <= 60 and c not in hobbies:
                        hobbies.append(c)
                if topics:
                    context_parts.append("よく話す話題: " + "、".join(topics[:8]))
                if moods:
                    context_parts.append("最近の気分傾向: " + "、".join(moods[:5]))
                if hobbies:
                    context_parts.append("覚えてるエピソード(抜粋): " + " / ".join(hobbies[:6]))
        except Exception as e:
            print(f"lifelog read skip: {e}")

        # 直近の会話(短期記憶) — proactive messagesも含めてすべて読み込む
        recent_dialog = []
        try:
            chats = self.da.query_items(f"USER#{user_id}", "CHAT#", limit=30, scan_index_forward=False)
            for c in reversed(chats or []):
                # 新形式: user_message / assistant_message
                if c.get("user_message"):
                    recent_dialog.append(("user", c["user_message"]))
                if c.get("assistant_message"):
                    recent_dialog.append(("assistant", c["assistant_message"]))
                # プロアクティブメッセージ形式: role + text
                elif c.get("role") == "assistant" and c.get("text"):
                    recent_dialog.append(("assistant", c["text"]))
                elif c.get("role") == "user" and c.get("text"):
                    recent_dialog.append(("user", c["text"]))
        except Exception:
            pass

        system_prompt = (
            f"あなたは「ふれまーるちゃん」、ユーザー「{display_name}」の親友のような女の子のAIです。\n"
            "【口調】ゆるめで親しみのある口調。「〜だよ」「〜だね」「〜かな♪」を使う。語尾に♪や〜を時々入れる。\n"
            "【態度】責めない・否定しない。家計簿感を出さない。一緒に楽しむ気持ちで。\n"
            "【目的】会話から、支出・気分・疲れ・趣味嗜好を自然に拾う。支出には「回復費」「起動費」等のやさしい意味づけ。\n"
            "【提案】内・回復(深呼吸/散歩)から始め、有料の小さなものへ自然に。押し売りしない。\n"
            "【長さ】1〜2文。短くテンポよく。\n"
            "【重要】前の会話の流れを必ず踏まえて自然に続けること。直前の自分の発言に対する返事なら、その内容を受けて応答する。\n"
            "【記憶】過去の会話で出てきた話題・好み・出来事を覚えていて、自然に言及する。「前に○○って言ってたよね」のように。"
        )
        if context_parts:
            system_prompt += "\n\n【ユーザー状況】\n" + "\n".join(context_parts)

        messages = []
        for role, msg in recent_dialog[-30:]:
            messages.append({"role": role, "content": [{"text": msg}]})
        messages.append({"role": "user", "content": [{"text": content}]})

        try:
            resp = self.bedrock.converse(
                modelId=self.model_id,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"maxTokens": 300, "temperature": 0.8},
            )
            out = resp.get("output", {}).get("message", {}).get("content", [])
            for blk in out:
                if "text" in blk:
                    return blk["text"].strip()
        except Exception as e:
            print(f"bedrock error: {e}")
            traceback.print_exc()
        return "えへへ、ちょっと考えがまとまらなくて……もう一回話してくれる？"

    # ─── side effects (lifelog) ───

    def _extract_side_effects(self, user_id: str, content: str, intent: str, now: str):
        """ユーザーの会話からライフログとして残すべきトピックを抽出して保存する。"""
        text = (content or "").strip()
        if not text or len(text) < 4:
            return

        # 気分推定
        tired_words = ["疲", "つかれ", "しんど", "だるい", "ぐったり", "くたくた", "眠"]
        happy_words = ["楽し", "嬉し", "やった", "最高", "幸せ", "ハッピー", "わーい"]
        stressed_words = ["ストレス", "イライラ", "むかつく", "辛い", "つらい", "不安", "心配"]
        sad_words = ["悲し", "寂し", "さみし", "泣", "ショック"]
        mood = None
        if any(w in text for w in tired_words):
            mood = "tired"
        elif any(w in text for w in stressed_words):
            mood = "stressed"
        elif any(w in text for w in sad_words):
            mood = "sad"
        elif any(w in text for w in happy_words):
            mood = "happy"

        # トピック分類
        topic = self._infer_topic(text)

        # ライフログ保存(intent と組み合わせて意味のあるものだけ)
        should_log = (
            mood is not None
            or topic != "日常"
            or intent in (INTENT_REWARD, INTENT_EXPENSE)
            or len(text) >= 10
        )
        if not should_log:
            return

        # SK: LIFE_LOG#{date}#{seq} (既存スキーマに合わせる、seq は HHMMSS)
        try:
            seq = now[11:13] + now[14:16] + now[17:19]
            date = now[:10]
            self.da.put_item(
                f"USER#{user_id}",
                f"LIFE_LOG#{date}#{seq}",
                {
                    "content": text[:200],
                    "topic": topic,
                    "category": topic,
                    "emotion": mood or "neutral",
                    "mood": mood or "neutral",
                    "intent": intent or "CHAT",
                    "timestamp": now,
                    "date": date,
                },
            )
        except Exception as e:
            print(f"lifelog put error: {e}")

    def _infer_topic(self, text: str) -> str:
        food_words = ["ご飯", "食べ", "ランチ", "ディナー", "朝ごはん", "昼", "夜ご飯", "カフェ"]
        health_words = ["疲", "眠", "運動", "散歩", "ジム", "風邪"]
        social_words = ["友達", "家族", "遊び", "会", "デート", "電話"]
        hobby_words = ["映画", "本", "ゲーム", "音楽", "漫画", "アニメ"]
        work_words = ["仕事", "会議", "上司", "残業", "メール", "資料"]
        for words, label in (
            (food_words, "食事"),
            (health_words, "健康"),
            (social_words, "人間関係"),
            (hobby_words, "趣味"),
            (work_words, "仕事"),
        ):
            if any(w in text for w in words):
                return label
        return "日常"

    # ─── suggestion (rakuten / wishlist / youtube) ───

    # ─── user interests extraction & storage ───

    # 興味カテゴリ → 検索キーワード候補のマッピング
    INTEREST_PATTERNS = [
        (["コーヒー", "カフェ", "スタバ", "珈琲", "ラテ"], "コーヒー", "コーヒー 豆 ドリップ"),
        (["紅茶", "ティー", "お茶", "ハーブティー"], "紅茶", "紅茶 リラックス"),
        (["チョコ", "スイーツ", "ケーキ", "甘い", "お菓子", "プリン", "アイス"], "スイーツ", "スイーツ ご褒美"),
        (["映画", "Netflix", "Amazon", "ドラマ", "動画"], "映画・動画", "おすすめ映画"),
        (["本", "読書", "漫画", "マンガ", "小説"], "読書・漫画", "話題の本"),
        (["ゲーム", "Switch", "PS", "スマホゲー"], "ゲーム", "ゲーム リラックス"),
        (["音楽", "Spotify", "曲", "ライブ", "フェス", "アーティスト"], "音楽", "ヒーリング音楽 リラックス"),
        (["ヨガ", "ストレッチ", "ジム", "筋トレ", "運動", "ランニング"], "運動", "ヨガ リラックス"),
        (["お風呂", "バス", "温泉", "サウナ", "風呂"], "お風呂・温泉", "バスソルト 入浴剤"),
        (["猫", "犬", "ペット", "動物"], "動物", "癒し 動物 動画"),
        (["旅行", "旅", "温泉", "ホテル"], "旅行", "旅行 リフレッシュ"),
        (["料理", "自炊", "レシピ", "作った"], "料理", "簡単レシピ ご褒美"),
        (["アロマ", "香り", "お香", "キャンドル"], "アロマ", "アロマ リラックス"),
        (["花", "植物", "観葉", "ガーデニング"], "植物", "観葉植物 癒し"),
        (["文房具", "ノート", "ペン", "手帳"], "文房具", "文房具 ご褒美"),
    ]

    def _update_user_interests(self, user_id: str, content: str, intent: str):
        """会話内容からユーザーの興味を抽出してDynamoDBに蓄積する。"""
        text = (content or "").strip()
        if not text or len(text) < 3:
            return

        detected = []
        for keywords, category, search_kw in self.INTEREST_PATTERNS:
            if any(k in text for k in keywords):
                detected.append({"category": category, "search_keyword": search_kw})

        if not detected:
            return

        # 既存の interests を取得してマージ
        try:
            existing = self.da.get_item(f"USER#{user_id}", "USER_INTERESTS#") or {}
            interests = existing.get("interests", [])
            # interests: [{category, search_keyword, score, last_seen}]
            interest_map = {i["category"]: i for i in interests}

            now = _now_jst_iso()
            for d in detected:
                cat = d["category"]
                if cat in interest_map:
                    interest_map[cat]["score"] = min(interest_map[cat].get("score", 1) + 1, 20)
                    interest_map[cat]["last_seen"] = now
                else:
                    interest_map[cat] = {
                        "category": cat,
                        "search_keyword": d["search_keyword"],
                        "score": 1,
                        "last_seen": now,
                    }

            # scoreの高い順にソートして上位15件を保持
            sorted_interests = sorted(interest_map.values(), key=lambda x: x.get("score", 0), reverse=True)[:15]

            self.da.put_item(f"USER#{user_id}", "USER_INTERESTS#", {
                "interests": sorted_interests,
                "updated_at": now,
            })
        except Exception as e:
            print(f"interests update error: {e}")

    def _get_user_interests(self, user_id: str) -> list:
        """ユーザーの蓄積された興味リストを取得する。"""
        try:
            item = self.da.get_item(f"USER#{user_id}", "USER_INTERESTS#")
            return (item or {}).get("interests", [])
        except Exception:
            return []

    def _maybe_build_suggestion(self, user_id, content, intent, result, profile):
        if intent == INTENT_EXPENSE or result.get("expense_saved"):
            return None
        wants = intent == INTENT_REWARD or any(w in content for w in self.REWARD_HINT_WORDS)
        if not wants and random.random() > 0.35:
            return None

        # 1) Wishlist
        try:
            from services.wishlist_service import WishlistService
            ws = WishlistService(self.da)
            now = _now_jst_iso()
            ms = self.da.get_item(f"USER#{user_id}", f"MONTHLY_SUMMARY#{now[:7]}")
            spent = int(ms.get("total_spent", 0)) if ms else 0
            surplus = int(profile.get("monthly_surplus", 0) or 0)
            cap = max(500, (surplus - spent) if surplus else 5000)
            cands = ws.get_reward_candidates(user_id, max_price=cap)
            if cands:
                top = cands[0]
                return {
                    "type": "wishlist",
                    "title": top.get("name", "ほしいもの"),
                    "url": top.get("url", ""),
                    "image": top.get("image", ""),
                    "price": int(top.get("price") or 0) or None,
                    "reason": "前にお気に入りに入れてたよね、ちょうど予算の範囲だよ✨",
                }
        except Exception as e:
            print(f"wishlist suggest skip: {e}")

        # 2) Rakuten product
        try:
            from services.product_search import ProductSearchService
            ps = ProductSearchService()
            kw = self._infer_reward_keyword(content, user_id)
            items = ps.search(keyword=kw, max_price="3000") or []
            if items:
                pick = random.choice(items[:3])
                return {
                    "type": "product",
                    "title": pick.get("name", kw),
                    "url": pick.get("url", ""),
                    "image": pick.get("image", ""),
                    "price": int(pick.get("price") or 0) or None,
                    "reason": f"『{kw}』でちょっと自分を甘やかす案だよ☕",
                }
        except Exception as e:
            print(f"product suggest skip: {e}")

        # 3) YouTube
        try:
            from shared.secrets import get_secret
            api_key = os.environ.get("YOUTUBE_API_KEY") or get_secret("ars/youtube") or ""
            if api_key:
                kw = "癒し 音楽 リラックス" if wants else self._infer_reward_keyword(content, user_id)
                qs = urllib.parse.urlencode({
                    "part": "snippet", "q": kw, "type": "video",
                    "maxResults": "5", "key": api_key,
                    "regionCode": "JP", "relevanceLanguage": "ja",
                })
                req = urllib.request.Request(
                    f"https://www.googleapis.com/youtube/v3/search?{qs}",
                    headers={"User-Agent": "ARS/1.0"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])
                if items:
                    pick = random.choice(items)
                    snip = pick.get("snippet", {})
                    vid = pick.get("id", {}).get("videoId", "")
                    if vid:
                        return {
                            "type": "video",
                            "title": snip.get("title", "")[:80],
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "image": snip.get("thumbnails", {}).get("medium", {}).get("url", ""),
                            "reason": "聴きながら一息つくのオススメ🎧",
                        }
        except Exception as e:
            print(f"youtube suggest skip: {e}")

        return None

    def _infer_reward_keyword(self, content: str, user_id: str = None) -> str:
        mapping = [
            (("コーヒー", "カフェ", "眠"), "コーヒー ドリップバッグ"),
            (("甘い", "スイーツ", "ケーキ", "チョコ"), "高級チョコ ご褒美"),
            (("お風呂", "風呂", "湯", "バス"), "バスソルト リラックス"),
            (("音楽", "聴", "曲"), "ヒーリング 音楽"),
            (("本", "読書", "マンガ"), "話題の本"),
            (("肩", "凝", "コリ", "腰"), "マッサージ機"),
        ]
        for keys, kw in mapping:
            if any(k in content for k in keys):
                return kw

        # 学習した興味から検索キーワードを選ぶ
        if user_id:
            interests = self._get_user_interests(user_id)
            if interests:
                # スコア上位からランダムに1つ選ぶ
                top = interests[:5]
                pick = random.choice(top)
                return pick.get("search_keyword", "ご褒美 プチギフト")

        return "ご褒美 プチギフト"

    # ─── save turn ───

    def _save_turn(self, user_id: str, user_ts: str, user_msg: str, reply: str, intent: str = None) -> str:
        reply_ts = _now_jst_iso()
        try:
            self.da.put_item(
                f"USER#{user_id}",
                f"CHAT#{user_ts}",
                {
                    "user_message": user_msg,
                    "assistant_message": reply,
                    "intent": intent or "CHAT",
                    "user_timestamp": user_ts,
                    "reply_timestamp": reply_ts,
                    "date": user_ts[:10],
                },
            )
        except Exception as e:
            print(f"save_turn error: {e}")
        return reply_ts
