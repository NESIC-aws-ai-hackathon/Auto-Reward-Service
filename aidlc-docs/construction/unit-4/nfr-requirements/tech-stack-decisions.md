# テックスタック決定 — Unit 4: ご褒美候補プール

**作成日**: 2026-05-16  
**Unit**: Unit 4 — ご褒美候補プール

---

## 確定テックスタック

Unit 4 は Unit 0〜2 で確立したスタックを継承し、楽天ウェブサービスAPI呼び出しと EventBridge Scheduler を追加する。

---

## 1. 外部API

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **商品検索API** | 楽天ウェブサービス 楽天市場商品検索API | 無料・AppID1つで利用可能。既存技術スタック確定済み |
| **APIドメイン** | `app.rakuten.co.jp/services/api/IchibaItem/Search/20170706` | 楽天公式ドキュメント（新ドメイン `openapi.rakuten.co.jp` は現状リダイレクト先。旧ドメインが安定） |
| **HTTPクライアント** | `requests` ライブラリ（既存 Layer に含まれる） | 追加パッケージ不要 |
| **認証方式** | `applicationId` クエリパラメータ | 楽天API標準方式 |
| **シークレット保存** | AWS Secrets Manager `ars/rakuten` に `RAKUTEN_APP_ID` 保存 | Unit 0 NFR Design で確定したサービス別分割構造に準拠 |

---

## 2. Lambda 関数（新規追加）

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **関数名** | `RewardPoolUpdaterFunction` | 命名規則: `{機能}Function` |
| **ハンドラ** | `src/handlers/reward_pool_updater.lambda_handler` | 既存パスパターン準拠 |
| **メモリ** | 256 MB | バッチ処理。大きなデータ変換なし |
| **タイムアウト** | 300 秒（5分） | 50ユーザー × 5キーワード × 1秒/req = 250秒 + バッファ |
| **ランタイム** | python3.13 | プロジェクト統一 |
| **Lambda Layer** | `ArsCommonLayer` 継承 | `requests`, `pydantic` 含む |
| **イベントソース** | EventBridge Scheduler | 日次バッチ |
| **同時実行** | 1（EventBridge から直接呼び出し） | バッチは並列化不要（レートリミット対応のため直列処理） |

---

## 3. EventBridge Scheduler

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **スケジュール式** | `cron(0 17 * * ? *)` | UTC 17:00 = JST 02:00（深夜バッチ）。JSTオフセット +9h |
| **Flexible Time Window** | OFF（`FLEXIBLE_TIME_WINDOW_OFF`） | 深夜2時に正確に実行したい |
| **フェイルオーバー** | なし（翌日に自動再実行される設計） | ハッカソンスコープ |
| **SAMリソース名** | `RewardPoolScheduler` | 命名規則準拠 |

---

## 4. DynamoDB アクセスパターン（Unit 4 追加分）

| エンティティ | PK | SK | 操作 |
|---|---|---|---|
| ご褒美候補プール | `USER#{userId}` | `REWARD_POOL#` | GetItem / PutItem |
| 嗜好メモリ（読み取りのみ） | `USER#{userId}` | `PREF_MEMORY#` | GetItem |
| ユーザープロファイル（読み取りのみ） | `USER#{userId}` | `PROFILE#` | GetItem（GSI scan でPK一覧取得） |

**GSI 活用**: 全ユーザーのPKを取得するため `entityType-index` GSI で `entity_type = "PROFILE"` を Scan/Query する。

---

## 5. IAM 権限

Unit 4 では Unit 0 で定義済みの `ArsLambdaRole` に **新規権限の追加は不要**。  
既存の DynamoDB CRUD 権限 + Secrets Manager 読み取り権限で動作する。

`RewardPoolUpdaterFunction` には以下の既存権限を継承:

```yaml
- Effect: Allow
  Action:
    - dynamodb:GetItem
    - dynamodb:PutItem
    - dynamodb:Query
    - dynamodb:Scan
  Resource:
    - !GetAtt ArsTable.Arn
    - !Sub "${ArsTable.Arn}/index/*"

- Effect: Allow
  Action:
    - secretsmanager:GetSecretValue
  Resource: !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:ars/rakuten*"
```

---

## 6. 環境変数（RewardPoolUpdaterFunction）

| 変数名 | 値（例） | 説明 |
|--------|---------|------|
| `TABLE_NAME` | `ArsTable` | DynamoDB テーブル名（Globals 継承） |
| `RAKUTEN_SECRET_NAME` | `ars/rakuten` | Secrets Manager シークレット名（楽天専用）|
| `RAKUTEN_DEFAULT_KEYWORDS` | `スイーツ,コスメ,本,入浴剤,アロマ` | 嗜好なしユーザー向けデフォルトキーワード |
| `RAKUTEN_MAX_ITEMS_PER_POOL` | `20` | プール最大アイテム数 |
| `RAKUTEN_HITS_PER_KEYWORD` | `5` | キーワードあたり取得件数 |

---

## 7. テスト方針

| テスト種別 | ライブラリ | 方針 |
|-----------|----------|------|
| ユニットテスト | `pytest` + `unittest.mock` | `requests.get` をモック化して楽天APIを模倣 |
| DynamoDB モック | `moto` または `unittest.mock` | Unit 2 同様の conftest パターンを継承 |
| LLMテスト | なし（Unit 4 は LLM 未使用） | — |
