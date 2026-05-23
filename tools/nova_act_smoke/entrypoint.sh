#!/bin/bash
# ECS コンテナ エントリポイント
# MODE 環境変数に応じて起動するプロセスを切り替え
#   - login: Amazon ログイン Web UI サーバーのみ
#   - worker: カート自動化ワーカーのみ
#   - all: 両方を並行起動 (デフォルト)

set -e

echo "=== ARS Nova Act Container ==="
echo "MODE: ${MODE:-all}"
echo "PROFILES_DIR: ${NOVA_ACT_PROFILES_DIR:-/data/profiles}"
echo "=============================="

case "${MODE}" in
    login)
        echo "Starting login server..."
        exec python /app/login_server.py
        ;;
    worker)
        echo "Starting worker..."
        exec python /app/worker.py
        ;;
    all)
        echo "Starting login server + worker..."
        # ログインサーバーをバックグラウンドで起動
        python /app/login_server.py &
        LOGIN_PID=$!
        # ワーカーをフォアグラウンドで起動
        python /app/worker.py &
        WORKER_PID=$!
        # どちらかが終了したら全体を停止
        wait -n $LOGIN_PID $WORKER_PID
        EXIT_CODE=$?
        echo "Process exited with code $EXIT_CODE, shutting down..."
        kill $LOGIN_PID $WORKER_PID 2>/dev/null || true
        exit $EXIT_CODE
        ;;
    *)
        echo "Unknown MODE: ${MODE}. Use 'login', 'worker', or 'all'."
        exit 1
        ;;
esac
