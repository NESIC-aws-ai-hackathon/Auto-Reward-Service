# Unit of Work プラン — オートリワードサービス

**作成日**: 2026-05-08

> **回答方法**: 各 `[Answer]:` タグの後に選択肢（A, B, C...）を記入してください。

---

## 実行チェックリスト

- [x] Q1〜Q4 への回答収集
- [x] unit-of-work.md 生成
- [x] unit-of-work-dependency.md 生成
- [x] unit-of-work-story-map.md 生成
- [ ] ユーザー承認

---

## 【Q1】Construction フェーズの Unit 実装単位

各 Unit をどの粒度で Construction フェーズの「1サイクル」として扱いますか？

A) **1 Unit = 1 サイクル** — U1 から U7 を順番に、1 Unit ずつ Functional Design → Code Generation → Test を完結させる  
B) **機能スライス単位** — 各 Unit の中でさらに機能（例: U2-01 手動入力のみ → U2-05 スコア算出 → ...）を小さく区切って実装する  
C) **フェーズ 1 まとめて** — U1 + U2 + U4（コアバリュー）を設計まで一度にやり、実装は後  
X) その他（以下に記述）

[Answer]: B

---

## 【Q2】共有パッケージ（packages/）の実装タイミング

`@ars/shared-types`, `@ars/shared-clients`, `@ars/shared-ai`, `@ars/shared-config` はどのタイミングで実装しますか？

A) **最初に全パッケージを実装**（スタブ含む） — U1 の実装前に共有パッケージを先行実装する  
B) **使う Unit が来たタイミングで都度実装** — U1 実装時に @ars/shared-config を、U2 実装時に @ars/shared-clients を追加する  
C) **共有パッケージを「Unit 0」として最初のサイクルで実装**  
X) その他（以下に記述）

[Answer]: C

---

## 【Q3】テスト実装のタイミング

A) **コード生成と同じサイクルで実装**（各 Unit の Code Generation に Unit テスト + 統合テストを含める）  
B) **コード生成後に別サイクルでテストを追加**  
X) その他（以下に記述）

[Answer]: A

---

## 【Q4】Docker Compose の実装タイミング

インフラ（`infrastructure/docker-compose.yml` と Nginx 設定）はいつ実装しますか？

A) **最初に実装**（共有パッケージと同じタイミングで Docker Compose の骨格を作る）  
B) **全 Unit のコード生成完了後にまとめて実装**  
C) **各 Unit のコード生成と並行して、そのサービスのコンテナ定義を追加していく**  
X) その他（以下に記述）

[Answer]: C
