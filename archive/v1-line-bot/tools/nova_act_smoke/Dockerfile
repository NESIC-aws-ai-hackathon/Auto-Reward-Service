# Nova Act Amazon Worker + Login Server Container
# - Ubuntu 22.04 + Python 3.11 + Playwright Chromium 一式
# - ECS Fargate での実行を想定
# - MODE=login: Amazon ログイン Web UI サーバー
# - MODE=worker: カート自動化ワーカー (DynamoDB ポーリング)
# - MODE=all: 両方を同時起動

FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL=1 \
    HOME=/home/nova \
    NOVA_ACT_USER_DATA_DIR=/home/nova/.nova-act/ars-amazon \
    NOVA_ACT_PROFILES_DIR=/data/profiles \
    MODE=all

# 非 root ユーザー
RUN useradd -m -s /bin/bash nova && \
    mkdir -p /app /home/nova/.nova-act /data/profiles && \
    chown -R nova:nova /app /home/nova /data/profiles

WORKDIR /app

COPY --chown=nova:nova requirements-nova-act.txt /app/
RUN pip install --no-cache-dir -r requirements-nova-act.txt

COPY --chown=nova:nova purchase_amazon.py worker.py login_server.py entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

USER nova

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
