.PHONY: build deploy layer-install test lint clean

# Lambda Layer の依存パッケージをインストール
layer-install:
	pip install -r requirements.txt -t layer/python/ --upgrade

# SAM ビルド
build:
	sam build

# SAM デプロイ
deploy: build
	sam deploy

# ユニットテスト
test:
	pytest tests/unit/ -v

# テスト（カバレッジ付き）
test-cov:
	pytest tests/unit/ -v --cov=layer/python --cov-report=term-missing

# 構文チェック
lint:
	python -m flake8 layer/python/ src/ --max-line-length=120

# 生成物クリーン
clean:
	rm -rf .aws-sam/
	find layer/python -name "*.pyc" -delete
	find layer/python -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find src -name "*.pyc" -delete
	find src -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
