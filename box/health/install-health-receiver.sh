#!/usr/bin/env bash
# Bitrone Box — установка приёмника health.json (HTTP, systemd).
# Запуск на коробке:  sudo bash install-health-receiver.sh [--port 8080]
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

PORT=8080
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    *) echo "неизвестный аргумент: $1"; exit 1;;
  esac
done

CFG=/etc/bitrone-box/box.conf
mkdir -p /etc/bitrone-box
touch "$CFG"

getcfg() { grep -E "^$1=" "$CFG" 2>/dev/null | tail -n1 | cut -d= -f2- || true; }
setcfg() { grep -qE "^$1=" "$CFG" && return 0; echo "$1=$2" >> "$CFG"; }

ROOT="$(getcfg HEALTH_ROOT)"; [ -n "$ROOT" ] || ROOT="/srv/bitrone/health"
setcfg HEALTH_ROOT "$ROOT"
setcfg HEALTH_PORT "$PORT"

TOKEN="$(getcfg HEALTH_TOKEN)"
if [ -z "$TOKEN" ]; then
  TOKEN="$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')"
  echo "HEALTH_TOKEN=$TOKEN" >> "$CFG"
  echo "[*] сгенерирован HEALTH_TOKEN"
fi
# box.conf читают службы под разными пользователями (restic/kiosk/bitrone) — оставляем 644
chmod 644 "$CFG"

echo "[*] системный пользователь bitrone + $ROOT"
id bitrone >/dev/null 2>&1 || useradd --system --home-dir /srv/bitrone --shell /usr/sbin/nologin bitrone
mkdir -p "$ROOT"
chown -R bitrone:bitrone "$(dirname "$ROOT")" "$ROOT"
chmod 755 "$ROOT"

echo "[*] приёмник → /opt/bitrone-box/health-receiver.py"
mkdir -p /opt/bitrone-box
install -m 0755 "$HERE/health-receiver.py" /opt/bitrone-box/health-receiver.py

cat >/etc/systemd/system/bitrone-health-receiver.service <<EOF
[Unit]
Description=Bitrone Box — приёмник health.json
After=network-online.target
Wants=network-online.target

[Service]
User=bitrone
Group=bitrone
ExecStart=/usr/bin/python3 /opt/bitrone-box/health-receiver.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now bitrone-health-receiver.service
sleep 1
systemctl --no-pager status bitrone-health-receiver.service | head -n 5 || true

IP="$(hostname -I | awk '{print $1}')"
echo
echo "================ приёмник health поднят ================"
echo "Слушает:   0.0.0.0:$PORT   (открой порт в firewall, если включён)"
echo "Пишет в:   $ROOT   (витрина читает отсюда)"
echo
echo "На сервере клиента в C:\\ProgramData\\Bitrone\\health.conf:"
echo "  HEALTH_URL=http://$IP:$PORT"
echo "  HEALTH_TOKEN=$TOKEN"
echo "======================================================="
