#!/usr/bin/env bash
# Deploy/redeploy to a VPS. Run from the repo root on a dev machine:
#   deploy/deploy.sh [ssh-host]        (default host: hostinger)
# Secrets are NOT shipped: /opt/reel-to-text/.env lives only on the server.
set -euo pipefail
HOST="${1:-hostinger}"
APP=/opt/reel-to-text

rsync -az --delete \
  --exclude '.git' --exclude '.env' --exclude '.venv' --exclude 'venv' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude 'data' \
  ./ "$HOST:$APP/"

ssh "$HOST" bash -s <<REMOTE
set -euo pipefail
id reel-to-text >/dev/null 2>&1 || useradd --system --home /var/lib/reel-to-text --shell /usr/sbin/nologin reel-to-text
install -d -o reel-to-text -g reel-to-text -m 700 /var/lib/reel-to-text
[ -d $APP/venv ] || python3 -m venv $APP/venv
$APP/venv/bin/pip install -q --upgrade pip >/dev/null
$APP/venv/bin/pip install -q --upgrade -r $APP/requirements.txt
[ -f $APP/.env ] || { echo "!! $APP/.env is missing — create it from .env.example"; exit 1; }
chown root:reel-to-text $APP/.env && chmod 640 $APP/.env
install -m 644 $APP/deploy/reel-to-text.service /etc/systemd/system/reel-to-text.service
install -m 644 $APP/deploy/reel-to-text-health.service /etc/systemd/system/reel-to-text-health.service
install -m 644 $APP/deploy/reel-to-text-health.timer /etc/systemd/system/reel-to-text-health.timer
systemctl daemon-reload
systemctl enable reel-to-text reel-to-text-health.timer >/dev/null 2>&1
systemctl restart reel-to-text
systemctl start reel-to-text-health.timer
sleep 6
systemctl is-active reel-to-text
journalctl -u reel-to-text -n 8 --no-pager -o cat
REMOTE
