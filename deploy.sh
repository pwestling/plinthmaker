#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="root@racknerd"
APP_SLUG="plinthmaker"
APP_DOMAIN="plinthmaker.thehivemind5.com"
REMOTE_APP_ROOT="/app/$APP_SLUG"
REMOTE_HTML_ROOT="$REMOTE_APP_ROOT/html"
REMOTE_SERVER_ROOT="$REMOTE_APP_ROOT/server"
REMOTE_NGINX_CONF="/etc/nginx/conf.d/$APP_SLUG.conf"
REMOTE_SERVICE_PATH="/usr/lib/systemd/system/$APP_SLUG-api.service"
SERVICE_NAME="$APP_SLUG-api"
DOCKER_IMAGE_TAG="$APP_SLUG:latest"
HEALTHCHECK_URL="http://127.0.0.1:8000/api/health"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  git diff --exit-code > /dev/null || {
    echo "Error: uncommitted changes"
    git diff
    exit 1
  }

  git diff --cached --exit-code > /dev/null || {
    echo "Error: staged but uncommitted changes"
    git diff --cached
    exit 1
  }
fi

uv run python -m unittest discover -s tests

ssh "$REMOTE_HOST" <<EOF
set -euo pipefail
mkdir -p "$REMOTE_HTML_ROOT"
mkdir -p "$REMOTE_SERVER_ROOT"
cat > "$REMOTE_HTML_ROOT/index.html" <<'HTML'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>plinthmaker</title>
  </head>
  <body>
    <p>plinthmaker deployment bootstrap page</p>
  </body>
</html>
HTML
EOF

scp -r app src static templates "$REMOTE_HOST:$REMOTE_SERVER_ROOT/"
scp main.py pyproject.toml uv.lock Dockerfile "$REMOTE_HOST:$REMOTE_SERVER_ROOT/"
scp nginx.conf "$REMOTE_HOST:$REMOTE_NGINX_CONF"
scp "server/$APP_SLUG-api.service" "$REMOTE_HOST:$REMOTE_SERVICE_PATH"

ssh "$REMOTE_HOST" <<EOF
set -euo pipefail

cd "$REMOTE_SERVER_ROOT"
docker build -t "$DOCKER_IMAGE_TAG" .

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

if systemctl is-active --quiet "$SERVICE_NAME"; then
  systemctl restart "$SERVICE_NAME"
else
  systemctl start "$SERVICE_NAME"
fi

for i in {1..45}; do
  if curl -f -s "$HEALTHCHECK_URL" > /dev/null; then
    echo "Service is healthy"
    break
  fi
  if [ \$i -eq 45 ]; then
    echo "Service failed healthcheck"
    systemctl status "$SERVICE_NAME" --no-pager
    exit 1
  fi
  sleep 1
done

nginx -t
systemctl reload nginx
EOF
