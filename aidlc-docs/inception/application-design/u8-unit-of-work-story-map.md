# Unit 8: Unit of Work — 機能要件マッピング

## 機能要件 → Unit マッピング

| 機能要件 | Unit | 実装内容 |
|---------|------|---------|
| FR-8-01: 音声チャット | **U8-B** | WebRTC接続、ephemeral key、Transcript収集 |
| FR-8-01: 音声チャット（認証） | **U8-A** | Cognito認証後にセッション開始可能 |
| FR-8-02: ライフログ | **U8-C** | Transcript → Claude Sonnet → LIFE_LOG# |
| FR-8-03: 日記サマリ | **U8-C** | ライフログ → Claude Sonnet → DAILY_FUREMARU_SUMMARY# + Push |
| FR-8-04: 余剰金ダッシュボード | **U8-E** | 余剰金・支出推移・カテゴリ内訳の表示UI |
| FR-8-05: ストレス判定 | **U8-D** | 複合判定 → STRESS_SUMMARY# |
| FR-8-06: 段階的ご褒美誘導 | **U8-D** | RecoveryProvider + RecoveryView |
| FR-8-07: Web Push通知 | **U8-C** | サブスクリプション管理 + 通知送信 |
| FR-8-08: Cognito認証 | **U8-A** | User Pool + デモログイン + JWT管理 |
| FR-8-09: アバター表示 | **U8-B** | 静止画 + 音声時軽微アニメ |

---

## コンポーネント → Unit マッピング

| ID | コンポーネント | Unit | 備考 |
|----|--------------|------|------|
| C01 | PWA Shell | U8-A | React SPA骨格 |
| C02 | VoiceChat | U8-B | WebRTC + アバター |
| C03 | Dashboard | U8-E | 余剰金・支出表示 |
| C04 | DiaryView | U8-E | 日記表示・読み上げ |
| C05 | RecoveryView | U8-D | 回復案カードUI |
| C06 | AuthModule | U8-A | Cognito認証React |
| C07 | ApiGateway | U8-A（骨格）→ U8-B〜E（ルート追加） | 段階的に拡張 |
| C08 | VoiceSessionService | U8-B | ephemeral key |
| C09 | TranscriptService | U8-B | Transcript保存 |
| C10 | AnalysisWorker | U8-C（LifeLog/Diary）+ U8-D（Stress） | 非同期Lambda |
| C11 | PushService | U8-C | Web Push |
| C12 | RecoveryProvider | U8-D | 回復案生成 |
| C13 | CognitoAuth | U8-A | SAMリソース |
| C14 | DataAccess | U8-A（初回）→ 全Unit共有 | 共通モジュール |
| C15 | BedrockClient | U8-C（初回）→ U8-D共有 | 共通モジュール |

---

## DynamoDB エンティティ → Unit マッピング

| エンティティSK | 作成Unit | 読取Unit |
|---------------|---------|---------|
| `PROFILE#` | U8-A | 全Unit |
| `VOICE_SESSION#{sessionId}` | U8-B | U8-C |
| `CONVERSATION_TURN#{timestamp}` | U8-B | U8-C, U8-D |
| `LIFE_LOG#{date}#{seq}` | U8-C | U8-D, U8-E |
| `DAILY_FUREMARU_SUMMARY#{date}` | U8-C | U8-E |
| `STRESS_SUMMARY#{date}` | U8-D | U8-E |
| `EXPENSE#{timestamp}` | U8-C (分析由来) / U8-D (手動) | U8-E |
| `REWARD_PERMIT#{timestamp}` | U8-D | U8-E |
| `REWARD_SKIP#{timestamp}` | U8-D | U8-E |
| `MONTHLY_SUMMARY#{yyyy-mm}` | U8-C | U8-E |
| `PUSH_SUBSCRIPTION#` | U8-C | U8-C |
| `ANALYSIS_JOB#{jobId}` | U8-B (作成) | U8-C (処理・完了) |
| `IDENTITY#COGNITO#{sub}` | U8-A | 全Unit |

---

## 各Unitの推定規模

| Unit | Frontend | Backend | テスト | 推定工数 |
|------|----------|---------|--------|---------|
| U8-A | React初期構成 + 認証画面 | Lambda骨格 + DataAccess | 認証フロー + CRUD | Medium |
| U8-B | WebRTC接続 + チャットUI | VoiceSession + Transcript | セッションライフサイクル | Large |
| U8-C | Push購読UI（小） | AnalysisWorker + Push + Bedrock | 分析パイプライン | Large |
| U8-D | RecoveryView | Recovery + Stress判定 | 回復案生成ロジック | Medium |
| U8-E | Dashboard + DiaryView | API追加（小） | UI統合 | Medium |
