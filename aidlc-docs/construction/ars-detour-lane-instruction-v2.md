# ARS 追加機能指示書 v2：寄り道レーン（PWA 実装）

## 概要

既存の Auto-Reward-Service（ARS）に「寄り道レーン」機能を追加する。
**PWA（Progressive Web App）として実装し、LIFF には依存しない。**

> **「疲れた日の帰り道を、フレマールちゃんが実際の寄り道ルートに変える」**
>
> ユーザーが「今日もう無理」「帰り道で甘えたい」と送るだけで、
> 現在地から寄り道できるスポットをフレマールちゃんが提案する。
> ARS はただの家計簿ではなく「現実の帰り道に誘惑を差し込むアプリ」になる。

---

## v1 → v2 変更点

| 項目 | v1 | v2 |
|---|---|---|
| **キャラクター** | リワードちゃん | **フレマールちゃん** 🇫🇷 |
| **フロント実装** | LIFF（LINE 内ブラウザ） | **PWA**（独立 Web アプリ） |
| **ホスティング** | LIFF エンドポイント | **S3 + CloudFront** または API Gateway |
| **認証** | LIFF SDK（ID Token） | **LINE Login（OAuth 2.0）** |
| **Push 通知** | LINE Push（月200通制限） | **Web Push（無制限）** |
| **位置情報** | LIFF 内ブラウザ依存（不安定） | **PWA Geolocation API（確実）** |
| **オフライン** | ❌ | **✅ Service Worker** |
| **ホーム画面** | ❌ | **✅ インストール可能** |

---

## PWA を採用する理由

1. **Push 通知が LINE の月200通制限に縛られない** → Web Push で無制限
2. **Geolocation が確実に動く** → LIFF 内ブラウザの制約を回避
3. **ホーム画面にインストール** → ネイティブアプリ感
4. **オフライン対応** → Service Worker でキャッシュ
5. **LINE 以外からもアクセス可能** → 将来の拡張性

---

## 既存アーキテクチャとの整合

| 要素 | 既存仕様 | 本機能での対応 |
|---|---|---|
| キャラクター | フレマールちゃん 🇫🇷 | そのまま ✅ |
| ベース URL | `https://6seky2k0ge.execute-api.ap-northeast-1.amazonaws.com` | API はそのまま。PWA は別ドメイン |
| LIFF | `2010106872-9t0gN1D6`（ダッシュボード等） | 寄り道レーンは **PWA** で実装 |
| DynamoDB | ArsTable（単一テーブル設計 PK=USER#{id}） | SK=TEMPTATION_SESSION#{id} 追加 |
| Lambda 層 | `layer/python/services/`, `layer/python/models/` | `location_service.py`, `temptation_engine.py` 追加 |
| ハンドラー | `src/handlers/` | `pwa_temptation.py` 追加 |
| プロンプト | `src/prompts/` | `temptation_prompt.py` 追加 |
| Intent 分類 | EXPENSE / REWARD / GREET / CHAT 等 | `TEMPTATION` 追加 |
| Bedrock | Nova Lite / Nova Micro | そのまま ✅ |
| Runtime | Python 3.14 | そのまま ✅ |

---

## 1. ユーザーストーリー（US-9: 寄り道レーン）

```
疲れて帰る社会人として、
私は「今日もう無理」と LINE で話しかけるだけで、
現在地から寄り道できるスポットをフレマールちゃんに提案してほしい。
それによって、自分で店や買うものを考えずに、
自然とお金を使う帰り道に乗れるようにしたい。
```

---

## 2. 全体フロー

```
ユーザー: 「今日もう無理。帰り道で甘えたい」
  ↓
webhook_handler → intent_classifier → TEMPTATION
  ↓
temptation_engine.invite_location()
  ↓
Reply:
  「今日はまっすぐ帰る日じゃないです🇫🇷
   現在地から、寄り道できるスポットを探しますね！
   下のボタンから開いてください✨」
  [🗺️ 寄り道レーンを作る]  ← PWA URL
  ↓
PWA 起動 → LINE Login で認証 → Geolocation API で現在地取得
  ↓
POST /api/temptation/start (lat, lng, message)
  ↓
location_service.search_nearby_reward_places()
  ↓
temptation_engine.build_lanes()
  ↓
PWA 画面に寄り道レーン3件表示
  ↓
ユーザーが「この寄り道で帰る」をタップ
  ↓
POST /api/temptation/accept
  ↓
後日: 「カフェ 680円」→ EXPENSE# に temptation_session_id 紐付け
```

---

## 3. PWA アーキテクチャ

### 3.1 構成

```
┌─────────────────────────────────────────────┐
│  PWA（フロント）                              │
│  - React / Next.js (static export)           │
│  - S3 + CloudFront                           │
│  - manifest.json + service-worker.js         │
│  - LINE Login SDK                            │
│  URL: https://ars-pwa.example.com            │
│       or CloudFront ディストリビューション     │
└──────────────────┬──────────────────────────┘
                   │ HTTPS
                   ▼
┌─────────────────────────────────────────────┐
│  API（バックエンド）                          │
│  - API Gateway + Lambda（既存）              │
│  - /api/temptation/start                     │
│  - /api/temptation/accept                    │
│  - /api/temptation/history                   │
│  - /api/push/subscribe (Web Push 登録)       │
│  URL: https://6seky2k0ge.execute-api...      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  DynamoDB / Bedrock / Location API           │
└─────────────────────────────────────────────┘
```

### 3.2 PWA マニフェスト

```json
// public/manifest.json
{
  "name": "フレマール・寄り道レーン",
  "short_name": "寄り道レーン",
  "description": "フレマールちゃんが今日の帰り道を甘やかします",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#FFF5F5",
  "theme_color": "#E63946",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

### 3.3 Service Worker

```javascript
// public/service-worker.js

const CACHE_NAME = 'ars-detour-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icons/icon-192.png',
];

// インストール時にキャッシュ
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

// オフライン時はキャッシュから返す
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

// Web Push 受信
self.addEventListener('push', (event) => {
  const data = event.data?.json() ?? {};
  event.waitUntil(
    self.registration.showNotification(data.title || 'フレマールちゃん', {
      body: data.body || '寄り道しない？🇫🇷',
      icon: '/icons/icon-192.png',
      badge: '/icons/badge-72.png',
      data: { url: data.url || '/' },
    })
  );
});

// 通知クリック
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
```

### 3.4 LINE Login 認証

```typescript
// lib/auth.ts

const LINE_LOGIN_CHANNEL_ID = process.env.NEXT_PUBLIC_LINE_LOGIN_CHANNEL_ID;
const REDIRECT_URI = process.env.NEXT_PUBLIC_REDIRECT_URI;

export function getLineLoginUrl(): string {
  const state = crypto.randomUUID();
  sessionStorage.setItem('line_login_state', state);

  return (
    `https://access.line.me/oauth2/v2.1/authorize` +
    `?response_type=code` +
    `&client_id=${LINE_LOGIN_CHANNEL_ID}` +
    `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}` +
    `&state=${state}` +
    `&scope=profile%20openid`
  );
}

// コールバックで code を受け取り、バックエンドで token 交換
export async function handleCallback(code: string): Promise<string> {
  const res = await fetch('/api/auth/line-callback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  const { access_token, user_id } = await res.json();
  localStorage.setItem('ars_token', access_token);
  localStorage.setItem('ars_user_id', user_id);
  return user_id;
}
```

---

## 4. Intent 分類への追加

### 4.1 TEMPTATION Intent

既存の `intent_classifier.py` に追加：

```python
TEMPTATION = "TEMPTATION"
```

### 4.2 検出パターン

| ユーザーの発言例 | Intent |
|---|---|
| 「今日もう無理」 | TEMPTATION |
| 「帰り道で甘えたい」 | TEMPTATION |
| 「ご飯作りたくない」 | TEMPTATION |
| 「まっすぐ帰れない」 | TEMPTATION |
| 「なんか寄り道したい」 | TEMPTATION |
| 「疲れた、どっか寄りたい」 | TEMPTATION |
| 「自炊無理」 | TEMPTATION |
| 「コンビニ寄っていい？」 | TEMPTATION |

### 4.3 webhook_handler での分岐

```python
elif intent == "TEMPTATION":
    reply = temptation_engine.invite_location(user_id, user_message)
    line_service.reply_message(reply_token, reply)
```

---

## 5. 寄り道レーンの種類

| lane_type | レーン名 | 想定金額 | ARS カテゴリ | 検索対象 |
|---|---|---|---|---|
| `CAFE_REBOOT` | カフェ再起動レーン | 500〜900円 | 情緒安定費 | カフェ, コーヒー, ベーカリー |
| `CONVENIENCE_RECOVERY` | コンビニ回復レーン | 300〜600円 | 回復費 | コンビニ, スイーツ |
| `SELF_COOKING_ESCAPE` | 自炊放棄レーン | 800〜1,500円 | グルメ費 | レストラン, ラーメン, 惣菜 |
| `LOW_COST_RECOVERY` | 低コスト回復レーン | 200〜500円 | 回復費 | コンビニ, ドラッグストア |
| `RICHER_ESCAPE` | ちょっと贅沢レーン | 1,500〜3,000円 | グルメ費 | レストラン, デザート |

---

## 6. Location Service

### 6.1 ホットペッパーグルメ API（推奨）

無料 + 日本の飲食店に特化 + 位置検索対応。

```python
# layer/python/services/location_service.py

import os
import json
import urllib.request
from typing import Optional

HOTPEPPER_API_KEY = os.environ.get("HOTPEPPER_API_KEY", "")
USE_MOCK_LOCATION = os.environ.get("USE_MOCK_LOCATION", "false") == "true"

# lane_type → ホットペッパー genre コード
LANE_TYPE_TO_GENRE = {
    "CAFE_REBOOT": ["G014"],           # カフェ・スイーツ
    "CONVENIENCE_RECOVERY": [],         # ホットペッパーにコンビニなし→モック
    "SELF_COOKING_ESCAPE": ["G013", "G009"],  # ラーメン, 中華
    "LOW_COST_RECOVERY": [],            # モック
    "RICHER_ESCAPE": ["G001", "G006"],  # イタリアン, 洋食
}


def search_nearby_reward_places(
    lat: float,
    lng: float,
    lane_type: str,
    radius_m: int = 800,
) -> list[dict]:
    if USE_MOCK_LOCATION:
        return _mock_places_nearby(lat, lng, lane_type)

    genres = LANE_TYPE_TO_GENRE.get(lane_type, [])
    if not genres:
        return _mock_places_nearby(lat, lng, lane_type)

    # ホットペッパー range: 1=300m, 2=500m, 3=1000m
    range_code = 2 if radius_m <= 500 else 3
    results = []

    for genre in genres:
        url = (
            f"https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
            f"?key={HOTPEPPER_API_KEY}"
            f"&lat={lat}&lng={lng}"
            f"&range={range_code}"
            f"&genre={genre}"
            f"&format=json"
            f"&count=3"
        )
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            shops = data.get("results", {}).get("shop", [])
            for shop in shops:
                results.append({
                    "name": shop.get("name"),
                    "category": shop.get("genre", {}).get("name", ""),
                    "lat": float(shop.get("lat", 0)),
                    "lng": float(shop.get("lng", 0)),
                    "address": shop.get("address", ""),
                    "url": shop.get("urls", {}).get("pc", ""),
                    "photo": shop.get("photo", {}).get("mobile", {}).get("s", ""),
                    "budget": shop.get("budget", {}).get("average", ""),
                    "distance_m": _calc_distance(lat, lng, float(shop.get("lat", 0)), float(shop.get("lng", 0))),
                })

    results.sort(key=lambda x: x["distance_m"])
    return results[:5]


def _mock_places_nearby(lat: float, lng: float, lane_type: str) -> list[dict]:
    mock_data = {
        "CAFE_REBOOT": [
            {"name": "駅前カフェ", "category": "カフェ", "distance_m": 180, "budget": "~800円"},
            {"name": "タリーズコーヒー", "category": "カフェ", "distance_m": 350, "budget": "~600円"},
        ],
        "CONVENIENCE_RECOVERY": [
            {"name": "セブンイレブン", "category": "コンビニ", "distance_m": 80, "budget": "~500円"},
            {"name": "ファミリーマート", "category": "コンビニ", "distance_m": 200, "budget": "~400円"},
        ],
        "SELF_COOKING_ESCAPE": [
            {"name": "一蘭", "category": "ラーメン", "distance_m": 400, "budget": "~1,000円"},
            {"name": "松屋", "category": "牛丼", "distance_m": 150, "budget": "~600円"},
        ],
        "LOW_COST_RECOVERY": [
            {"name": "ローソン", "category": "コンビニ", "distance_m": 100, "budget": "~300円"},
        ],
        "RICHER_ESCAPE": [
            {"name": "イタリアンダイニング", "category": "イタリアン", "distance_m": 500, "budget": "~2,500円"},
        ],
    }
    places = mock_data.get(lane_type, [])
    for p in places:
        p["lat"] = lat + 0.001
        p["lng"] = lng + 0.001
        p["address"] = "モックデータ"
        p["url"] = ""
        p["photo"] = ""
    return places
```

### 6.2 環境変数

```yaml
# template.yaml に追加
Environment:
  Variables:
    HOTPEPPER_API_KEY: !Ref HotpepperApiKey
    USE_MOCK_LOCATION: "false"
```

---

## 7. temptation_engine.py

```python
# layer/python/services/temptation_engine.py

import uuid
from datetime import datetime
from services import dynamodb_service, finance_engine, location_service, bedrock_service

# PWA の URL
PWA_BASE_URL = "https://ars-detour.example.com"

LANE_DEFINITIONS = {
    "CAFE_REBOOT": {
        "title": "カフェ再起動レーン ☕",
        "estimated_min": 500,
        "estimated_max": 900,
        "ars_category": "情緒安定費",
    },
    "CONVENIENCE_RECOVERY": {
        "title": "コンビニ回復レーン 🏪",
        "estimated_min": 300,
        "estimated_max": 600,
        "ars_category": "回復費",
    },
    "SELF_COOKING_ESCAPE": {
        "title": "自炊放棄レーン 🍜",
        "estimated_min": 800,
        "estimated_max": 1500,
        "ars_category": "グルメ費",
    },
    "LOW_COST_RECOVERY": {
        "title": "低コスト回復レーン 💊",
        "estimated_min": 200,
        "estimated_max": 500,
        "ars_category": "回復費",
    },
    "RICHER_ESCAPE": {
        "title": "ちょっと贅沢レーン ✨",
        "estimated_min": 1500,
        "estimated_max": 3000,
        "ars_category": "グルメ費",
    },
}


def invite_location(user_id: str, message: str) -> dict:
    """
    TEMPTATION intent 検出後、PWA を開くよう促す Reply メッセージを生成。
    """
    pwa_url = f"{PWA_BASE_URL}?intent=detour"

    return {
        "type": "template",
        "altText": "寄り道レーンを作ります🇫🇷",
        "template": {
            "type": "buttons",
            "text": (
                "今日はまっすぐ帰る日じゃないです🇫🇷\n"
                "現在地から、寄り道できるスポットを探しますね！\n"
                "下のボタンから開いてください✨"
            ),
            "actions": [
                {
                    "type": "uri",
                    "label": "🗺️ 寄り道レーンを作る",
                    "uri": pwa_url,
                }
            ],
        },
    }


def build_lanes(user_id: str, lat: float, lng: float, message: str) -> dict:
    """現在地・残予算・嗜好から寄り道レーン3件を生成。"""
    budget = finance_engine.get_monthly_remaining(user_id)
    prefs = dynamodb_service.get_all_preferences(user_id)

    # 残予算に応じてレーン構成を決定
    if budget < 1000:
        lane_types = ["LOW_COST_RECOVERY", "CONVENIENCE_RECOVERY", "CAFE_REBOOT"]
    elif budget < 5000:
        lane_types = ["CAFE_REBOOT", "CONVENIENCE_RECOVERY", "SELF_COOKING_ESCAPE"]
    else:
        lane_types = ["CAFE_REBOOT", "SELF_COOKING_ESCAPE", "RICHER_ESCAPE"]

    lanes = []
    for lt in lane_types:
        places = location_service.search_nearby_reward_places(lat, lng, lt)
        if not places:
            continue
        definition = LANE_DEFINITIONS[lt]
        lane = {
            "lane_id": f"lane_{lt.lower()}_{uuid.uuid4().hex[:8]}",
            "lane_type": lt,
            "title": definition["title"],
            "estimated_min": definition["estimated_min"],
            "estimated_max": definition["estimated_max"],
            "ars_category": definition["ars_category"],
            "places": places,
            "recommendation_score": _calculate_score(lt, budget, prefs, places),
        }
        lanes.append(lane)

    lanes.sort(key=lambda x: x["recommendation_score"], reverse=True)
    reason = _generate_reason(user_id, message, lanes, budget)

    # セッション保存
    session_id = str(uuid.uuid4())
    session = {
        "session_id": session_id,
        "status": "proposed",
        "trigger_message": message,
        "created_at": datetime.now().isoformat(),
        "location": {"lat": lat, "lng": lng, "source": "pwa_geolocation"},
        "lanes": lanes,
        "recommended_lane_id": lanes[0]["lane_id"] if lanes else None,
        "selected_lane_id": None,
        "completed_expense_id": None,
    }
    dynamodb_service.put_item(
        pk=f"USER#{user_id}",
        sk=f"TEMPTATION_SESSION#{session_id}",
        item=session,
        ttl_days=30,
    )

    return {
        "session_id": session_id,
        "lanes": lanes,
        "recommended_lane_id": lanes[0]["lane_id"] if lanes else None,
        "reason": reason,
    }


def _calculate_score(lane_type, budget, prefs, places):
    base = 50
    if places:
        avg_distance = sum(p["distance_m"] for p in places) / len(places)
        if avg_distance < 200:
            base += 20
        elif avg_distance < 500:
            base += 10
    definition = LANE_DEFINITIONS[lane_type]
    if definition["estimated_max"] <= budget * 0.1:
        base += 15
    food_likes = prefs.get("food", {}).get("likes", [])
    if lane_type == "SELF_COOKING_ESCAPE" and any("ラーメン" in l for l in food_likes):
        base += 20
    return min(base, 100)


def _generate_reason(user_id, message, lanes, budget):
    if not lanes:
        return "うーん、近くにいい場所が見つからなかった…ごめんね🇫🇷"
    top_lane = lanes[0]
    prompt = f"""
あなたはフレマールちゃんです。フランス語と日本語を混ぜた上品だけど親しみやすい口調で話します。
ユーザーが「{message}」と言っています。
残予算は{budget}円です。
おすすめの寄り道レーンは「{top_lane['title']}」で、
近くに{top_lane['places'][0]['name']}があります（徒歩{top_lane['places'][0]['distance_m']//80}分）。
想定金額は{top_lane['estimated_min']}〜{top_lane['estimated_max']}円です。

2〜3行で、このレーンをおすすめする理由をフレマールちゃんの口調で書いてください。
    """
    return bedrock_service.invoke_text(prompt)
```

---

## 8. PWA 画面デザイン

### 8.1 URL

```
https://ars-detour.example.com/
  or
https://{cloudfront-dist}.cloudfront.net/
```

### 8.2 画面フロー

#### 初回アクセス（未認証）

```
┌─────────────────────────────────────┐
│  🇫🇷 フレマール・寄り道レーン        │
│                                     │
│  今日はまっすぐ帰る日じゃ           │
│  ないかもしれません。               │
│                                     │
│  現在地から寄り道できる             │
│  甘やかしスポットを探します。       │
│                                     │
│       [LINE でログイン]             │
│                                     │
│  💡 ホーム画面に追加すると          │
│    もっと便利に使えます！           │
└─────────────────────────────────────┘
```

#### ログイン済み → 位置情報取得

```
┌─────────────────────────────────────┐
│  🇫🇷 寄り道レーン                    │
│                                     │
│  現在地から、今日の甘やかしスポット │
│  を探しますね！                     │
│                                     │
│       [📍 現在地から探す]           │
│                                     │
└─────────────────────────────────────┘
```

#### 位置情報取得中

```
┌─────────────────────────────────────┐
│                                     │
│  フレマールちゃんが近くの           │
│  甘やかしスポットを                 │
│  探しています...🔍                  │
│                                     │
│  [ローディングアニメーション]       │
│                                     │
└─────────────────────────────────────┘
```

#### 位置情報拒否時（フォールバック）

```
┌─────────────────────────────────────┐
│                                     │
│  現在地がわからなかったので、       │
│  駅名やエリア名で探しますね！       │
│                                     │
│  [              テキスト入力        ]│
│  例: 東京駅、流山おおたかの森       │
│                                     │
│       [この場所で探す]              │
│                                     │
└─────────────────────────────────────┘
```

#### 結果表示

```
┌─────────────────────────────────────┐
│  🇫🇷 今日の寄り道レーン              │
│                                     │
│  ⭐ おすすめ                        │
│  ┌────────────────────────────────┐ │
│  │ ☕ カフェ再起動レーン           │ │
│  │ 駅前カフェ（徒歩3分）          │ │
│  │ 想定 500〜900円                │ │
│  │ [この寄り道で帰る]             │ │
│  └────────────────────────────────┘ │
│                                     │
│  ┌────────────────────────────────┐ │
│  │ 🏪 コンビニ回復レーン           │ │
│  │ セブンイレブン（徒歩1分）      │ │
│  │ 想定 300〜600円                │ │
│  │ [この寄り道で帰る]             │ │
│  └────────────────────────────────┘ │
│                                     │
│  ┌────────────────────────────────┐ │
│  │ 🍜 自炊放棄レーン              │ │
│  │ 一蘭（徒歩5分）                │ │
│  │ 想定 800〜1,500円              │ │
│  │ [この寄り道で帰る]             │ │
│  └────────────────────────────────┘ │
│                                     │
│  💬 フレマールちゃんのおすすめ:     │
│  「Aujourd'hui はカフェで一度       │
│   人間に戻ってから帰りましょう？    │
│   駅前のカフェ、近いですし✨」      │
│                                     │
│  ── 予算情報 ──                     │
│  今月の残り: 14,350円               │
│  ご褒美枠の消化: 40%                │
│                                     │
└─────────────────────────────────────┘
```

---

## 9. Web Push 通知

### 9.1 概要

LINE Push の月200通制限を超えるために、PWA の Web Push を活用。

### 9.2 サブスクリプション登録

```typescript
// lib/push.ts

export async function subscribePush(userId: string): Promise<void> {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY,
  });

  await fetch('/api/push/subscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('ars_token')}`,
    },
    body: JSON.stringify({
      user_id: userId,
      subscription: subscription.toJSON(),
    }),
  });
}
```

### 9.3 バックエンド（Web Push 送信）

```python
# layer/python/services/web_push_service.py

import json
from pywebpush import webpush, WebPushException

VAPID_PRIVATE_KEY = os.environ["VAPID_PRIVATE_KEY"]
VAPID_CLAIMS = {"sub": "mailto:ars@example.com"}


def send_web_push(subscription_info: dict, title: str, body: str, url: str = "/"):
    payload = json.dumps({"title": title, "body": body, "url": url})
    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
    except WebPushException as e:
        logger.error(f"Web Push failed: {e}")
```

### 9.4 DynamoDB

```
PK=USER#{id}  SK=WEB_PUSH_SUBSCRIPTION#
{
  "endpoint": "https://fcm.googleapis.com/...",
  "keys": { "p256dh": "...", "auth": "..." },
  "created_at": "2026-05-17T20:00:00+09:00"
}
```

---

## 10. API エンドポイント

### 10.1 POST /api/temptation/start

```
Request:
{
  "lat": 35.681236,
  "lng": 139.767125,
  "message": "今日もう無理。帰り道で甘えたい"
}
Header: Authorization: Bearer {line_access_token}

Response:
{
  "session_id": "uuid",
  "lanes": [...],
  "recommended_lane_id": "lane_cafe_reboot_xxx",
  "reason": "Aujourd'hui はカフェで..."
}
```

### 10.2 POST /api/temptation/accept

```
Request: { "session_id": "uuid", "lane_id": "lane_cafe_reboot_xxx" }
Response: { "accepted": true, "lane_id": "lane_cafe_reboot_xxx" }
```

### 10.3 GET /api/temptation/history

```
Response:
{
  "this_month": {
    "total_detours": 7,
    "by_lane": {
      "CAFE_REBOOT": {"count": 3, "total": 2040},
      "CONVENIENCE_RECOVERY": {"count": 4, "total": 1860}
    },
    "frequent_places": ["駅前カフェ", "セブンイレブン"]
  }
}
```

### 10.4 POST /api/push/subscribe

```
Request: { "user_id": "xxx", "subscription": {...} }
Response: { "subscribed": true }
```

### 10.5 POST /api/auth/line-callback

```
Request: { "code": "authorization_code" }
Response: { "access_token": "xxx", "user_id": "Uxxx" }
```

---

## 11. DynamoDB データモデル

```
PK=USER#{id}  SK=TEMPTATION_SESSION#{session_id}
{
  "session_id": "uuid",
  "status": "proposed" | "accepted" | "navigating" | "completed" | "cancelled",
  "trigger_message": "今日もう無理。帰り道で甘えたい",
  "created_at": "2026-05-17T20:00:00+09:00",
  "location": {
    "lat": 35.681236,
    "lng": 139.767125,
    "source": "pwa_geolocation" | "text_input"
  },
  "lanes": [...],
  "recommended_lane_id": "lane_cafe_reboot_xxx",
  "selected_lane_id": null,
  "completed_expense_id": null,
  "ttl": 1718668800
}
```

---

## 12. 支出記録との連携

```
ユーザーがレーンを accept
  → status = "accepted"
  → ユーザーが実際にお店に行く
  → LINE で「カフェ 680円」or レシート画像を送る
  → 既存の EXPENSE 記録フロー
  → EXPENSE# に以下を追加:
    {
      "temptation_session_id": "uuid",
      "lane_type": "CAFE_REBOOT",
      "place_name": "駅前カフェ",
      "location_based": true
    }
  → TEMPTATION_SESSION# の status を "completed" に更新
```

---

## 13. PWA ダッシュボード

```
┌─────────────────────────────────────┐
│  🗺️ 今月の寄り道レーン              │
│                                     │
│  ☕ カフェ再起動: 3回 / 2,040円      │
│  🏪 コンビニ回復: 4回 / 1,860円     │
│  🍜 自炊放棄: 2回 / 2,300円         │
│                                     │
│  まっすぐ帰れなかった回数: 7回      │
│                                     │
│  よく寄るスポット:                  │
│  1. 駅前カフェ                      │
│  2. セブンイレブン                  │
│  3. 一蘭                            │
└─────────────────────────────────────┘
```

---

## 14. template.yaml 追加

```yaml
PwaTemptationFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: src/handlers/pwa_temptation.handler
    Runtime: python3.14
    MemorySize: 512
    Timeout: 30
    Events:
      StartTemptation:
        Type: HttpApi
        Properties:
          Path: /api/temptation/start
          Method: POST
      AcceptTemptation:
        Type: HttpApi
        Properties:
          Path: /api/temptation/accept
          Method: POST
      TemptationHistory:
        Type: HttpApi
        Properties:
          Path: /api/temptation/history
          Method: GET

PwaAuthFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: src/handlers/pwa_auth.handler
    Runtime: python3.14
    MemorySize: 256
    Timeout: 10
    Events:
      LineCallback:
        Type: HttpApi
        Properties:
          Path: /api/auth/line-callback
          Method: POST

WebPushFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: src/handlers/web_push.handler
    Runtime: python3.14
    MemorySize: 256
    Timeout: 10
    Events:
      Subscribe:
        Type: HttpApi
        Properties:
          Path: /api/push/subscribe
          Method: POST
```

---

## 15. 新規ファイル一覧

| ファイル | 内容 |
|---|---|
| **バックエンド** | |
| `layer/python/services/location_service.py` | ホットペッパー API + モック |
| `layer/python/services/temptation_engine.py` | 寄り道レーン生成・管理 |
| `layer/python/services/web_push_service.py` | Web Push 送信 |
| `src/handlers/pwa_temptation.py` | 寄り道 API ハンドラー |
| `src/handlers/pwa_auth.py` | LINE Login コールバック |
| `src/handlers/web_push.py` | Web Push サブスクリプション |
| `src/prompts/temptation_prompt.py` | Bedrock プロンプト |
| **PWA フロント** | |
| `pwa/public/manifest.json` | PWA マニフェスト |
| `pwa/public/service-worker.js` | Service Worker |
| `pwa/src/pages/index.tsx` | メイン画面（位置取得→レーン表示） |
| `pwa/src/pages/history.tsx` | 寄り道履歴 |
| `pwa/src/lib/auth.ts` | LINE Login 認証 |
| `pwa/src/lib/push.ts` | Web Push 登録 |
| `pwa/src/lib/api.ts` | API クライアント |

---

## 16. テストケース

| # | ケース | 期待結果 |
|---|---|---|
| 1 | 「今日もう無理」と LINE に送信 | Intent=TEMPTATION → PWA ボタン Reply |
| 2 | PWA で LINE Login | 認証成功 → ユーザー ID 取得 |
| 3 | PWA で lat/lng 付き POST | 3件のレーン + おすすめ理由が返る |
| 4 | lat/lng なし（位置情報拒否） | テキスト入力フォールバック |
| 5 | 残予算 < 1,000円 | LOW_COST_RECOVERY が最上位 |
| 6 | 残予算 > 5,000円 | RICHER_ESCAPE が含まれる |
| 7 | PREF_MEMORY にラーメン好き | SELF_COOKING_ESCAPE のスコアが上がる |
| 8 | accept 後に「カフェ 680円」 | EXPENSE に temptation_session_id 紐付け |
| 9 | モック環境 | USE_MOCK_LOCATION=true でモックデータが返る |
| 10 | Web Push 登録 | WEB_PUSH_SUBSCRIPTION# に保存 |
| 11 | PWA ホーム画面追加 | manifest.json に基づきインストール |
| 12 | オフラインアクセス | Service Worker がキャッシュから返す |
| 13 | ダッシュボード | 今月の寄り道回数・レーン別支出表示 |
| 14 | フレマールちゃん表記 | 全メッセージでフレマールちゃんの口調 |

---

## 17. 実装優先度

| 優先度 | 機能 | 理由 |
|---|---|---|
| **P0** | TEMPTATION intent 追加 | 全ての起点 |
| **P0** | PWA 基盤（manifest + SW + LINE Login） | PWA の土台 |
| **P0** | POST /api/temptation/start | レーン生成の中核 |
| **P0** | location_service（モック込み） | デモで動くことが最優先 |
| **P0** | PWA 結果表示画面 | デモ映え |
| **P1** | accept + 支出記録連携 | 寄り道→記録の一連フロー |
| **P1** | Web Push 通知 | LINE 200通制限を超える |
| **P1** | ダッシュボード「まっすぐ帰れなかった回数」 | 審査員インパクト |
| **P2** | ホットペッパー API 本実装 | モックで動けば OK |
| **P2** | オフライン対応 | UX 向上 |

# ARS 寄り道レーン v3 追加指示：ご褒美提案の統合

## 概要

v2（PWA + フレマールちゃん）の寄り道レーンに、既存のご褒美提案機能を統合する。

> **「どこに寄る？」+「何を買う？」を一体化し、帰り道の意思決定をゼロにする。**
>
> ユーザーは場所もモノも考える必要がない。
> フレマールちゃんが「ここに寄って、これを買おう」まで全部決める。

---

## 1. v2 → v3 変更点

| 項目 | v2 | v3 |
|---|---|---|
| **レーン内容** | 場所のみ | **場所 + おすすめ商品/メニュー** |
| **REWARD_POOL** | 未連携 | **レーンごとにご褒美候補をマッチング** |
| **Bedrock 生成** | おすすめ理由のみ | **理由 + 具体的な「これ買って」提案** |
| **PREF_MEMORY** | スコア調整のみ | **嗜好データで商品をパーソナライズ** |
| **おすすめ（US-4）** | LINE postback 独立 | **PWA 内にも統合** |
| **購入記録** | LINE で手入力 | **PWA「買った！」ボタン追加** |
| **ダッシュボード** | 寄り道回数のみ | **寄り道 × ご褒美 複合分析** |

---

## 2. 統合後のレーン構造

### 2.1 レーン + ご褒美提案の統合データ

```json
{
  "lane_id": "lane_cafe_reboot_abc12345",
  "lane_type": "CAFE_REBOOT",
  "title": "カフェ再起動レーン ☕",
  "estimated_min": 500,
  "estimated_max": 900,
  "ars_category": "情緒安定費",
  "places": [
    {
      "name": "駅前カフェ",
      "distance_m": 180,
      "budget": "~800円"
    }
  ],
  "rewards": [
    {
      "reward_id": "rw_001",
      "name": "季節限定マンゴーフラペチーノ",
      "price": 680,
      "source": "bedrock_generated",
      "match_reason": "甘いもの好き + カフェ系",
      "emoji": "🥭"
    },
    {
      "reward_id": "rw_002",
      "name": "濃厚チーズケーキ",
      "price": 520,
      "source": "pref_memory_match",
      "match_reason": "前回カフェでケーキ買って満足度高かった",
      "emoji": "🍰"
    }
  ],
  "recommendation_score": 88
}
```

### 2.2 lane_type ごとのご褒美マッチング

| lane_type | ご褒美カテゴリ | 具体例 |
|---|---|---|
| `CAFE_REBOOT` | スイーツ, ドリンク, ベーカリー | フラペチーノ, チーズケーキ, クロワッサン |
| `CONVENIENCE_RECOVERY` | コンビニスイーツ, 小さなご褒美 | プレミアムプリン, ハーゲンダッツ, 新作チョコ |
| `SELF_COOKING_ESCAPE` | がっつり系, ラーメントッピング | 替玉, トッピング全部乗せ, サイドメニュー追加 |
| `LOW_COST_RECOVERY` | 低コスト回復アイテム | 栄養ドリンク, ガム, 入浴剤 |
| `RICHER_ESCAPE` | ちょっと贅沢体験 | デザートセット, ワイン1杯, 特別コース |

---

## 3. ご褒美提案ロジック

### 3.1 reward_matcher.py（新規）

```python
# layer/python/services/reward_matcher.py

from services import dynamodb_service, bedrock_service


def match_rewards_to_lane(
    user_id: str,
    lane_type: str,
    places: list[dict],
    budget_remaining: int,
) -> list[dict]:
    """レーンに合うご褒美候補を2〜3件生成する。"""

    # 1. PREF_MEMORY から嗜好を取得
    prefs = dynamodb_service.get_all_preferences(user_id)
    food_likes = prefs.get('food', {}).get('likes', [])
    recent_rewards = dynamodb_service.get_recent_rewards(user_id, days=30)

    # 2. REWARD_POOL から lane_type に合う候補を取得
    pool_items = dynamodb_service.get_reward_pool_by_category(
        user_id, _lane_to_reward_category(lane_type)
    )

    # 3. Bedrock でパーソナライズ提案を生成
    generated = _generate_personalized_rewards(
        lane_type, places, food_likes, budget_remaining, recent_rewards
    )

    # 4. POOL + 生成 を統合してスコア順に並べる
    all_rewards = pool_items + generated
    all_rewards.sort(key=lambda x: x.get('score', 0), reverse=True)
    return all_rewards[:3]


def _lane_to_reward_category(lane_type: str) -> list[str]:
    mapping = {
        'CAFE_REBOOT': ['情緒安定費', '趣味費'],
        'CONVENIENCE_RECOVERY': ['回復費'],
        'SELF_COOKING_ESCAPE': ['グルメ費'],
        'LOW_COST_RECOVERY': ['回復費', '緊急回復費'],
        'RICHER_ESCAPE': ['グルメ費', '美容費'],
    }
    return mapping.get(lane_type, ['回復費'])


def _generate_personalized_rewards(
    lane_type, places, food_likes, budget, recent_rewards
) -> list[dict]:
    place_names = ', '.join(p['name'] for p in places[:2])
    likes_str = ', '.join(food_likes[:5]) if food_likes else 'まだわからない'
    recent_str = ', '.join(r.get('name', '') for r in recent_rewards[:3])

    prompt = (
        f"あなたはフレマールちゃんです。\n"
        f"ユーザーの好み: {likes_str}\n"
        f"最近のご褒美: {recent_str}\n"
        f"予算残り: {budget}円\n"
        f"寄り道先: {place_names}\n"
        f"レーン: {lane_type}\n\n"
        f"この寄り道先で買えそうなおすすめ商品・メニューを2つ、\n"
        f"商品名、想定価格、おすすめ理由を含むJSONで返してください。\n"
        f"ユーザーの好みと最近のご褒美を考慮してください。"
    )
    result = bedrock_service.invoke_text(prompt)
    return _parse_reward_json(result)
```

### 3.2 temptation_engine.py への統合

```python
# build_lanes() に reward_matcher を追加

from services import reward_matcher

def build_lanes(user_id, lat, lng, message):
    # ... 既存のレーン生成ロジック ...

    for lane in lanes:
        # 各レーンにご褒美提案を追加
        lane['rewards'] = reward_matcher.match_rewards_to_lane(
            user_id=user_id,
            lane_type=lane['lane_type'],
            places=lane['places'],
            budget_remaining=budget,
        )

    # ... 以降は同じ ...
```

---

## 4. PWA 画面更新

### 4.1 レーンカード（ご褒美付き）

```
┌────────────────────────────────────┐
│ ☕ カフェ再起動レーン                │
│ 駅前カフェ（徒歩3分）               │
│ 想定 500〜900円                     │
│                                    │
│ 🎁 フレマールちゃんのおすすめ:       │
│ ┌────────────────────────────────┐  │
│ │ 🥭 季節限定マンゴーフラペチーノ │  │
│ │    680円                       │  │
│ └────────────────────────────────┘  │
│ ┌────────────────────────────────┐  │
│ │ 🍰 濃厚チーズケーキ            │  │
│ │    520円                       │  │
│ │    💬 前回も美味しかったよね？   │  │
│ └────────────────────────────────┘  │
│                                    │
│ [この寄り道で帰る]                  │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│ 🏪 コンビニ回復レーン               │
│ セブンイレブン（徒歩1分）           │
│ 想定 300〜600円                     │
│                                    │
│ 🎁 フレマールちゃんのおすすめ:       │
│ ┌────────────────────────────────┐  │
│ │ 🍮 セブンプレミアム 濃厚プリン  │  │
│ │    298円                       │  │
│ │    💬 プリン好きって言ってたよね │  │
│ └────────────────────────────────┘  │
│ ┌────────────────────────────────┐  │
│ │ 🍨 ハーゲンダッツ 新作           │  │
│ │    351円                       │  │
│ └────────────────────────────────┘  │
│                                    │
│ [この寄り道で帰る]                  │
└────────────────────────────────────┘
```

### 4.2 「買った！」ボタン（accept 後の画面）

```
┌────────────────────────────────────┐
│ 🇫🇷 寄り道中...                      │
│                                    │
│ ☕ カフェ再起動レーン                │
│ 駅前カフェ                          │
│                                    │
│ フレマールちゃんのおすすめ:          │
│ • 🥭 マンゴーフラペチーノ (680円)   │
│ • 🍰 チーズケーキ (520円)           │
│                                    │
│ ── 何を買った？ ──                  │
│                                    │
│ [🥭 フラペチーノ買った！ 680円]     │
│ [🍰 チーズケーキ買った！ 520円]     │
│ [✏️ 別のものを記録する]              │
│                                    │
│ ── or ──                           │
│ [📸 レシートを撮影して記録]          │
│                                    │
│ [🏠 まっすぐ帰った]                 │
└────────────────────────────────────┘
```

### 4.3 ワンタップ支出記録フロー

```
ユーザーが「🥭 フラペチーノ買った！680円」をタップ
  ↓
POST /api/temptation/complete
  {
    "session_id": "uuid",
    "lane_id": "lane_cafe_reboot_xxx",
    "reward_id": "rw_001",
    "amount": 680,
    "item_name": "マンゴーフラペチーノ",
    "place_name": "駅前カフェ"
  }
  ↓
EXPENSE# 自動作成（手入力不要！）
  {
    "amount": 680,
    "category": "情緒安定費",
    "item_name": "マンゴーフラペチーノ",
    "temptation_session_id": "uuid",
    "lane_type": "CAFE_REBOOT",
    "place_name": "駅前カフェ",
    "location_based": true,
    "reward_id": "rw_001"
  }
  ↓
TEMPTATION_SESSION# → status = 'completed'
  ↓
MONTHLY_SUMMARY# 更新
  ↓
フレマールちゃん Reply（Web Push or LINE）:
  「マンゴーフラペチーノ、Bon choix！🥭
   今月の情緒安定費はあと 4,320円。
   Très bien、いい使い方です✨」
```

---

## 5. 追加 API

### 5.1 POST /api/temptation/complete

```
Request:
{
  "session_id": "uuid",
  "lane_id": "lane_cafe_reboot_xxx",
  "reward_id": "rw_001",
  "amount": 680,
  "item_name": "マンゴーフラペチーノ",
  "place_name": "駅前カフェ"
}

Response:
{
  "expense_id": "exp_xxx",
  "budget_remaining": 4320,
  "message": "マンゴーフラペチーノ、Bon choix！🥭 ..."
}
```

### 5.2 GET /api/rewards/for-lane

```
Request: ?lane_type=CAFE_REBOOT&lat=35.68&lng=139.76

Response:
{
  "rewards": [
    {"name": "季節限定フラペチーノ", "price": 680, "emoji": "🥭"},
    {"name": "濃厚チーズケーキ", "price": 520, "emoji": "🍰"}
  ]
}
```

---

## 6. 「ついでに」提案（寄り道後のオンラインご褒美）

### 6.1 フロー

```
ユーザーが寄り道 complete → 「カフェ 680円」記録
  ↓
残予算がまだ余裕ある場合:
  ↓
フレマールちゃん:
  「カフェお疲れさま〜！🇫🇷
   そういえば、まだ今月 4,320円あるから
   ついでにこれどうかな？✨」

  ┌────────────────────────────┐
  │ 🛁 BARTH 入浴剤 (990円)    │
  │ 💬 疲れた日の夜にぴったり   │
  │ [楽天で見る] [買った！]      │
  └────────────────────────────┘
```

### 6.2 ロジック

```python
def suggest_online_reward_after_detour(user_id, session):
    remaining = finance_engine.get_monthly_remaining(user_id)
    if remaining < 500:
        return None  # 残予算少ない → 提案しない

    # 寄り道で使ったカテゴリと別カテゴリから提案
    used_category = session['lanes'][0]['ars_category']
    pool = dynamodb_service.get_reward_pool_exclude_category(
        user_id, exclude=used_category, max_price=remaining
    )
    if not pool:
        return None
    return pool[0]  # スコア最高のご褒美を1つ提案
```

---

## 7. 過去のご褒美を活用した提案

### 7.1 「前回の×× どうだった？」

```
ユーザーが同じ場所に2回目の寄り道:
  ↓
フレマールちゃん:
  「あっ、駅前カフェまた来たんですね！🇫🇷
   前回のチーズケーキ、美味しかった？
   
   今日のおすすめ:
   • 🍰 チーズケーキ（前回美味しかった？→リピート）
   • 🥭 新作マンゴータルト（新しいの試してみる？）」
```

### 7.2 DynamoDB: REWARD_HISTORY の活用

```
PK=USER#{id}  SK=EXPENSE#{ISO8601}
{
  "temptation_session_id": "uuid",
  "place_name": "駅前カフェ",
  "item_name": "チーズケーキ",
  "amount": 520,
  "satisfaction": null  // 後で聞く
}
```

翌日の Push で:

```
フレマールちゃん:
  「昨日の駅前カフェのチーズケーキ、どうだった？😊
   ⭐⭐⭐⭐⭐ で教えて！」

→ ユーザーが ⭐4 をタップ
→ EXPENSE の satisfaction = 4
→ 次回の提案スコアに反映
```

---

## 8. PWA ダッシュボード拡張（ご褒美 × 寄り道）

```
┌─────────────────────────────────────┐
│ 🇫🇷 今月のレポート                    │
│                                     │
│ ── 寄り道レーン ──                   │
│ まっすぐ帰れなかった回数: 7回        │
│ ☕ カフェ再起動: 3回 / 2,040円        │
│ 🏪 コンビニ回復: 4回 / 1,860円       │
│                                     │
│ ── ご褒美ランキング ──               │
│ 🥇 チーズケーキ (3回 / 1,560円) ⭐4.3│
│ 🥈 フラペチーノ (2回 / 1,360円) ⭐4.0│
│ 🥉 プレミアムプリン (3回 / 894円) ⭐5│
│                                     │
│ ── よく寄るスポット ──               │
│ 1. 駅前カフェ (5回)                  │
│ 2. セブンイレブン (4回)              │
│ 3. 一蘭 (2回)                        │
│                                     │
│ ── フレマールちゃんの分析 ──         │
│ 「あなたは水曜と金曜に寄り道しがち   │
│  です🇫🇷 カフェ率が高くて、チーズ     │
│  ケーキがお気に入りみたい✨」         │
│                                     │
└─────────────────────────────────────┘
```

---

## 9. 新規ファイル一覧（v2 に追加）

| ファイル | 内容 |
|---|---|
| `layer/python/services/reward_matcher.py` | レーン × ご褒美マッチング |
| `src/handlers/pwa_temptation.py` に追加 | `/api/temptation/complete` |
| `pwa/src/components/RewardCard.tsx` | ご褒美カード UI |
| `pwa/src/components/QuickRecord.tsx` | 「買った！」ボタン UI |
| `pwa/src/pages/history.tsx` 拡張 | ご褒美ランキング表示 |

---

## 10. 追加テストケース

| # | ケース | 期待結果 |
|---|---|---|
| 1 | CAFE_REBOOT レーン生成 | rewards に 2〜3件のスイーツ/ドリンクが含まれる |
| 2 | PREF_MEMORY にプリン好き | プリン系の reward が優先的に提案される |
| 3 | 「買った！」ボタンタップ | EXPENSE 自動作成 + session complete |
| 4 | 同じ場所に2回目の寄り道 | 前回の商品への言及がある |
| 5 | 寄り道 complete 後 | 残予算に余裕あれば「ついでに」提案 |
| 6 | 残予算 500円未満の complete 後 | 「ついでに」提案なし |
| 7 | satisfaction 評価 | EXPENSE の satisfaction 更新 → 次回スコア反映 |
| 8 | ダッシュボード | ご褒美ランキング + 寄り道回数が表示 |

---

## 11. 実装優先度（v2 に追加）

| 優先度 | 機能 | 理由 |
|---|---|---|
| **P0** | reward_matcher + レーンへの統合 | 「場所 + 商品」一体化がコア価値 |
| **P0** | 「買った！」ワンタップ記録 | 支出記録のハードルをゼロにする |
| **P0** | PWA レーンカード（ご褒美付き表示） | デモ映え |
| **P1** | 「ついでに」オンラインご褒美提案 | 寄り道→さらに消費の拡張 |
| **P1** | 過去のご褒美活用（リピート提案） | パーソナライズ感 |
| **P1** | satisfaction 評価 → スコア反映 | 提案精度の向上サイクル |
| **P2** | ダッシュボード（ご褒美ランキング） | 分析・可視化 |
| **P2** | 曜日別寄り道パターン分析 | フレマールちゃんの分析コメント |