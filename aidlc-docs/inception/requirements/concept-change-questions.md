# コンセプト変更に伴う要件確認質問

`docs/コンセプト変更定義書.md` の内容を分析し、新コンセプトでの開発を進めるにあたって確認が必要な項目をまとめました。
各質問の `[Answer]:` タグの後に選択肢の記号を記入してください。

---

## Question 1
MVPで実装するLINE Bot機能のスコープはどこまでですか？

A) 最小限（愚痴チャット + 支出チャット入力 + ご褒美相談のみ）
B) 標準（A + レシート画像解析 + 初回登録チャット + Push通知）
C) フル（B + LIFFダッシュボード + ご褒美候補プール日次バッチ + 口調カスタマイズ）
D) コンセプト変更定義書の記載通り全部（§1〜§20の全機能）
X) Other (please describe after [Answer]: tag below)

[Answer]: X) コンセプト変更定義書§1〜§20のうち、アフィリエイト実装とサービス強度の測定基盤を除いた全機能をMVP対象とする。

---

## Question 2
バックエンド技術スタックについて、コンセプト変更定義書では「Lambda / Backend」と記載されていますが、具体的にどの構成を想定していますか？

A) AWS Lambda（サーバーレス）+ API Gateway + DynamoDB — フルサーバーレス構成
B) AWS Lambda + API Gateway + DynamoDB + 一部 ECS/Fargate（バッチ処理用）
C) ECS/Fargate（コンテナ）+ DynamoDB — コンテナベース構成
D) ローカル開発優先（Docker Compose + Express/NestJS + DynamoDB Local）→ 後でLambdaに移行
X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 3
LLMモデルの選定について、コンセプト変更定義書では「Nova中心」とありますが、Amazon Bedrockを利用する前提ですか？

A) はい、Amazon Bedrock経由でNova Micro / Nova Liteを使う
B) Amazon Bedrock経由だが、Nova以外（Claude Haiku/Sonnet）も初期から併用する
C) LLMプロバイダーは未確定。コスト次第で OpenAI / Bedrock を選びたい
D) Bedrock前提だが、具体的なモデル選定は実装時に決めたい
X) Other (please describe after [Answer]: tag below)

[Answer]: Aで、試したいので変更できるようにしてもらえると助かる

---

## Question 4
レシート画像解析の実装方針はどうしますか？

A) Amazon Nova Lite（Bedrock）で画像→テキスト抽出
B) Amazon Textract でOCR → LLMで構造化
C) Claude（Vision）で画像解析
D) MVPではレシート画像解析は後回し（テキスト入力のみ）
X) Other (please describe after [Answer]: tag below)

[Answer]: X) MVPではAmazon Nova Liteを第一候補とする。精度が不足する場合はAmazon Textract + LLM構造化、またはClaude Visionへの切り替えも検討する。

---

## Question 5
DynamoDBのテーブル設計方針について確認します。コンセプト変更定義書§15のデータ種別（user_profile, fixed_costs, chat_logs, life_logs, pending_expense, expenses, preference_memory, reward_pool, reward_suggestions）をどう格納しますか？

A) シングルテーブルデザイン（1テーブルに全データ種別を格納、PK/SKで区別）
B) データ種別ごとに個別テーブル（9テーブル程度）
C) 関連データをグループ化した中間的な設計（3〜5テーブル程度）
D) 設計はお任せ（ベストプラクティスに従う）
X) Other (please describe after [Answer]: tag below)

[Answer]: A
LINEユーザーIDをPKにして、PROFILE#、EXPENSE#、LIFELOG#、REWARD_POOL# みたいにSKで分ける形。
---

## Question 6
LINE Messaging APIのプランについて確認します。Push通知の通数制限に関わります。

A) フリープラン（月200通まで、開発・検証用）
B) ライトプラン（月5,000通）
C) スタンダードプラン（月30,000通〜、追加メッセージ課金あり）
D) 未定（まずフリープランで開発し、後で変更する）
X) Other (please describe after [Answer]: tag below)

[Answer]: A
ハッカソン用なので最小限
開発でも数回pushするのみで考えている
デモの時はしっかり動かす
Pushは原則デモ用・1日1回設計。通常会話はユーザー起点のReply中心とする。

---

## Question 7
「ご褒美候補プール」の商品データはどこから取得しますか？

A) 手動登録（マスタデータとして事前に商品・カテゴリを登録）
B) 外部API連携（楽天API、Amazon Product Advertising API等）
C) LLMに生成させる（ユーザーの嗜好に基づいてLLMが候補を生成）
D) MVPでは手動登録、将来的にAPI連携を追加
X) Other (please describe after [Answer]: tag below)

[Answer]: B 楽天API利用

---

## Question 8
ユーザー認証・識別の方針を確認します。LINE Botの場合、LINEユーザーIDで識別できますが、追加の認証は必要ですか？

A) LINEユーザーIDのみで識別（追加認証なし）
B) LINEユーザーIDで識別 + LIFF利用時はLINEログインでアクセストークン取得
C) LINE連携 + 別途メールアドレス登録（将来のマルチプラットフォーム対応用）
D) 認証方針はお任せ
X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 9
開発の優先順位について、新コンセプトでのコアバリュー実装順序を確認します。

A) LINE Bot基盤 → 会話（愚痴・支出チャット）→ ご褒美提案 → レシート画像 → LIFF
B) LINE Bot基盤 → 初回登録フロー → 支出記録 → ご褒美候補プール → Push通知
C) LINE Bot基盤 → リワードちゃんの会話品質 → 支出抽出 → ご褒美提案 → その他
D) コンセプト変更定義書の記載順（§1〜§20）に従う
X) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 10
セキュリティ要件について、旧コンセプトでは「Security Baseline全ルール必須」としていましたが、新コンセプトでも同様ですか？

A) はい、同等のセキュリティレベルを維持する
B) MVPでは最低限（通信暗号化 + DynamoDB暗号化 + ログにPII出力禁止）に絞る
C) LINE Bot特有のセキュリティ（Webhook署名検証、チャネルシークレット管理）を重点的に
D) セキュリティ方針はお任せ（ベストプラクティスに従う）
X) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 11
プログラミング言語について確認します。旧コンセプトではTypeScript（NestJS）統一でしたが、Lambda + DynamoDB構成ではどうしますか？

A) TypeScript（Node.js Lambda）で統一
B) Python（Lambda）で統一
C) 処理に応じて使い分け（会話処理はPython、API/DB操作はTypeScript等）
D) お任せ（アーキテクチャに最適な言語を選定）
X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 12
旧コンセプトの「ストレスセンシング」機能は新コンセプトではどう扱いますか？コンセプト変更定義書では明示的なストレス入力UIは廃止され、会話から感情を読み取る方式に変わっていますが確認します。

A) 明示的なストレス入力は廃止。会話テキストからLLMが感情・疲労度を自動推定する
B) 会話からの自動推定が主だが、「今日どうだった？」的な質問で間接的に聞く
C) 旧コンセプトの5段階入力も残しつつ、会話からの推定を追加する
D) ストレスセンシング自体を廃止し、ユーザーの発話内容（「疲れた」「買いたい」等）のみで判断する
X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 13
テスト戦略について確認します。旧コンセプトではPBT（プロパティベーステスト）をPartialで有効にしていましたが、新コンセプトでも継続しますか？

A) はい、PBTも含めて同等のテスト戦略を維持する
B) ユニットテスト + 統合テストのみ（PBTは不要）
C) LLM応答のテストに重点を置く（プロンプトテスト・出力品質テスト）
D) テスト戦略はお任せ
X) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 14
コンセプト変更定義書§18の収益モデルについて、MVP段階でアフィリエイト機能を実装しますか？

A) MVPでは収益機能は実装しない（体験の完成度を優先）
B) MVPでもアフィリエイトリンク生成の仕組みは組み込む
C) 提携商品の候補プール混入のみ実装し、実際のアフィリエイト連携は後で
D) 収益モデルの実装範囲はお任せ
X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 15
「リワードちゃん」の口調カスタマイズ機能はMVPに含めますか？

A) MVPでは1つの口調（フレンドリー）のみ。口調カスタマイズは後のフェーズ
B) MVPで2〜3種類の口調を選べるようにする
C) MVPで全5種類（フレンドリー/やさしい敬語/小悪魔/お姉さん/ゆるふわ）を実装
D) お任せ
X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 16
IaC（Infrastructure as Code）についてどうしますか？

A) AWS CDK（TypeScript）で全インフラを定義
B) AWS SAM（Serverless Application Model）で Lambda + API Gateway を定義
C) Terraform で定義
D) MVPではIaCは使わず、手動 or AWS CLIでセットアップ
E) Serverless Framework を使用
X) Other (please describe after [Answer]: tag below)

[Answer]: B
