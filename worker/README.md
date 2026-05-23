# Nova Act Worker

Amazon 商品検索を行うブラウザ自動操作ワーカー。

## 重要方針

- **やること**: Amazon.co.jp で商品検索し、候補情報を抽出する
- **やらないこと**: ログイン、カート投入、購入操作、決済

## セットアップ

```bash
cd worker
pip install nova-act boto3
```

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| AWS_PROFILE | share | AWS プロファイル名 |
| AWS_REGION | ap-northeast-1 | リージョン |
| DDB_TABLE_NAME | ArsTable | DynamoDB テーブル名 |
| S3_SCREENSHOT_BUCKET | ars-nova-act-screenshots | スクリーンショット保存先 |
| POLL_INTERVAL | 5 | ポーリング間隔 (秒) |
| NOVA_ACT_PROFILE_DIR | (空) | ブラウザプロファイルパス (空でも可 - ログイン不要) |

## 実行

```bash
python nova_act_worker.py
```

## フロー

```
LIFF / LINE Bot → 候補検索リクエスト
    ↓
Backend API → DynamoDB に NOVA_ACT_SEARCH_JOB# (queued) を作成
    ↓
Worker がポーリング → queued ジョブ検出
    ↓
Nova Act でブラウザ操作:
  1. Amazon.co.jp を開く（ログイン不要）
  2. 検索バーにキーワード入力
  3. 検索結果から商品情報を抽出
  4. 商品名・価格・ASIN・画像URLを取得
  ※ カート投入・購入操作は絶対に行わない
    ↓
結果を DynamoDB に保存:
  - NOVA_ACT_SEARCH_JOB#{jobId} / RESULT# に検索結果
  - USER#{userId} / REWARD_POOL#{candidateId} に候補保存
    ↓
LIFF が候補表示 → ユーザーが「Amazonで確認する」「楽天で確認する」等で外部サイトへ
```

## ジョブステータス

| ステータス | 説明 |
|-----------|------|
| queued | ジョブ作成済み、ワーカー未着手 |
| processing | ワーカーが処理中 |
| completed | 検索完了、候補保存済み |
| failed | 失敗 |
