# NFR Requirements Plan — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16  
**ステータス**: 完了

---

## ユニット概要

Unit 0 は全 Lambda 関数が共通利用する基盤レイヤー。  
NFR の決定は Unit 1〜7 全体のパフォーマンス・コスト・セキュリティに直結する。

---

## 実行計画チェックリスト

- [x] Step 1: Functional Design 成果物分析
- [x] Step 2: NFR Requirements Plan 作成（本ファイル）
- [x] Step 3: 質問収集・回答受取
- [x] Step 4: 回答の曖昧さ解消（全問明確）
- [x] Step 5: NFR Requirements 成果物生成
  - [x] `nfr-requirements.md`
  - [x] `tech-stack-decisions.md`
- [ ] Step 6: 承認・次ステージへ進行

---

## 質問一覧（[Answer]: タグで回答してください）

### Q1: DynamoDB キャパシティモード

ArsTable のキャパシティモードを選択してください。  
MVP 段階はユーザー数が少ないため、コストとシンプルさのバランスが重要です。

A) **オンデマンド**（PAY_PER_REQUEST）— 使った分だけ課金。スケーリング不要でMVPに最適  
B) **プロビジョンド**（固定RCU/WCU）— 予測可能な低コスト。ただし設計・調整が必要  
C) **プロビジョンド + Auto Scaling**— 自動スケーリングで柔軟対応  
D) **オンデマンド**（dev環境）+ **プロビジョンド**（prod環境）で環境分離  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q2: Lambda メモリサイズ

Lambda 関数のメモリサイズを用途別に設定します。  
メモリを増やすとCPUも比例して上がり処理速度が向上しますが、コストも増加します。

A) 全関数統一: **256MB**（シンプル管理、MVPに十分）  
B) 全関数統一: **512MB**（Bedrock呼び出しや画像解析の余裕を考慮）  
C) 用途別:
   - Webhook / ルーティング系: 128MB
   - Bedrock テキスト系: 256MB
   - 画像解析（Nova Lite）系: 512MB
   - バッチ系（楽天API更新・Push通知）: 256MB  
D) 全関数統一: **128MB**（コスト最優先）  
E) その他（具体的に記述してください）

[Answer]: C

---

### Q3: Lambda タイムアウト

Lambda 関数のタイムアウト設定を選択してください。  
PERF-01 より LINE Reply は 3 秒以内が必須です。Webhook ハンドラはその前提で設定します。

A) 全関数統一: **30秒**（シンプル、ほぼ全ユースケースをカバー）  
B) 用途別:
   - Webhook Handler: **10秒**（3秒応答 + バッファ、タイムアウト前に Reply 優先）
   - Bedrock テキスト系: **30秒**
   - 画像解析系: **60秒**（PERF-02 非同期化前提）
   - バッチ系: **300秒**  
C) 用途別（より厳格）:
   - Webhook Handler: **5秒**
   - Bedrock テキスト系: **20秒**
   - 画像解析系: **60秒**
   - バッチ系: **300秒**  
D) 全関数統一: **60秒**  
E) その他（具体的に記述してください）

[Answer]: B

---

### Q4: Lambda Cold Start 対策（PERF-03）

Cold Start 対策を選択してください。  
Webhook Handler は LINE の 3 秒応答制約があるため最重要です。

A) **Provisioned Concurrency** を Webhook Handler のみに設定（最小: 1〜2）  
B) **EventBridge Scheduler でウォームアップ ping**（5分毎に Lambda を呼び出し）  
C) **対策なし**（MVP 段階は Cold Start を許容。問題になったら対処）  
D) Provisioned Concurrency（Webhook Handler）+ ウォームアップ ping（その他 Bedrock 系）  
E) その他（具体的に記述してください）

[Answer]: B

---

### Q5: AWS X-Ray トレーシング

分散トレーシング（X-Ray）の有効化範囲を選択してください。

A) **全Lambda関数で有効**（`aws-lambda-powertools` Tracer + SAM `Tracing: Active`）  
B) **Webhook Handler のみ有効**（ボトルネック特定に集中）  
C) **無効**（MVP 段階は CloudWatch Logs のみで十分）  
D) `aws-lambda-powertools` Tracer を使うが、**SAMでは PassThrough**（SDK はセットアップするが実際のトレースはしない）  
E) その他（具体的に記述してください）

[Answer]: C

---

### Q6: CloudWatch Logs 保持期間

Lambda 関数の CloudWatch Logs ロググループ保持期間を選択してください。

A) **30日**（MVP に十分、コスト最適）  
B) **7日**（コスト最優先）  
C) **90日**（デバッグ用に長めに保持）  
D) 用途別:
   - 通常 Lambda: 30日
   - バッチ系: 14日  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q7: Python ランタイムバージョン

Lambda の Python ランタイムバージョンを選択してください。

A) **Python 3.12**（現時点の最新 GA、パフォーマンス改善）  
B) **Python 3.11**（安定版、ライブラリ互換性が確認されている）  
C) **Python 3.10**  
D) **Python 3.13**（最新 preview）  
E) その他（具体的に記述してください）

[Answer]: 3.14

---

### Q8: AWS SAM デプロイリージョン

デプロイ先 AWS リージョンを選択してください。  
Bedrock Nova Micro / Nova Lite は一部リージョンのみ利用可能です。

A) **ap-northeast-1**（東京）— Bedrock Nova 対応、LINE ユーザーに物理的に近い  
B) **us-east-1**（バージニア）— Bedrock モデル対応が最も広い  
C) **ap-northeast-1**（prod）+ **us-east-1**（フォールバック用 Bedrock エンドポイント）  
D) **ap-southeast-1**（シンガポール）  
E) その他（具体的に記述してください）

[Answer]: A

