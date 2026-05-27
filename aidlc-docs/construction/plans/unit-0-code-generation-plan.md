# Code Generation Plan — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16  
**ステータス**: 完了

---

## 実行計画チェックリスト

- [x] Step 1: 全設計成果物（FD / NFR / Infra）レビュー完了
- [x] Step 2: Code Generation Plan 作成（本ファイル）
- [x] Step 3: コード生成
  - [x] スライス 0-1: プロジェクト基盤ファイル
  - [x] スライス 0-2: `schemas.py`
  - [x] スライス 0-3: `dynamodb_service.py`
  - [x] スライス 0-4: `bedrock_service.py`
  - [x] スライス 0-5: `line_service.py`
  - [x] スライス 0-6: `secrets.py`
  - [x] スライス 0-7: `logger.py`（`exceptions.py` 含む）
  - [x] スライス 0-8: `template.yaml`（ArsTable + ArsCommonLayer 完成版）
  - [x] スライス 0-9: `google_calendar_service.py`
- [x] Step 4: ユニットテスト生成
- [ ] Step 5: 承認・Unit 1 へ進行

---

## 生成ファイル一覧

| スライス | 生成ファイル | 配置パス |
|---------|------------|--------|
| 0-1 | `template.yaml` | `/` |
| 0-1 | `samconfig.toml` | `/` |
| 0-1 | `Makefile` | `/` |
| 0-1 | `requirements.txt` | `/` |
| 0-1 | `requirements-dev.txt` | `/` |
| 0-2 | `schemas.py` | `layer/python/models/` |
| 0-3 | `dynamodb_service.py` | `layer/python/services/` |
| 0-4 | `bedrock_service.py` | `layer/python/services/` |
| 0-5 | `line_service.py` | `layer/python/services/` |
| 0-6 | `secrets.py` | `layer/python/utils/` |
| 0-7 | `logger.py` | `layer/python/utils/` |
| 0-7 | `exceptions.py` | `layer/python/utils/` |
| 0-8 | `template.yaml`（ArsTable完成） | `/` |
| 0-9 | `google_calendar_service.py` | `layer/python/services/` |
| 各 | `__init__.py` × 3 | `layer/python/{services,utils,models}/` |
| テスト | `test_schemas.py` | `tests/unit/` |
| テスト | `test_dynamodb_service.py` | `tests/unit/` |
| テスト | `test_bedrock_service.py` | `tests/unit/` |
| テスト | `test_line_service.py` | `tests/unit/` |
| テスト | `test_secrets.py` | `tests/unit/` |
| テスト | `test_google_calendar_service.py` | `tests/unit/` |
| テスト | `conftest.py` | `tests/unit/` |

---

## 設計参照

| 設計書 | 参照内容 |
|--------|---------|
| `domain-entities.md` | Pydantic v2 モデル定義・TTL・GSI |
| `business-logic-model.md` | 全サービスのメソッドシグネチャ |
| `business-rules.md` | ルール R1-1〜R8-3 |
| `nfr-design-patterns.md` | リトライ・シングルトン・PII マスク |
| `logical-components.md` | Secrets Manager 構成・シングルトン初期化 |
| `infrastructure-design.md` | 環境変数・SAM 設定 |
