#!/usr/bin/env bash
# Установка службы экрана Bitrone Box на мини-ПК (Ubuntu/Debian).
#   sudo bash install-status.sh [--user restic] [--device /dev/sda]
# --user   — пользователь, от которого работает rest-server (служба читает его папку копий)
# --device — диск с копиями для проверки SMART
set -euo pipefail

USER_NAME=restic
DEVICE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --user) USER_NAME="$2"; shift 2 ;;
    --device) DEVICE="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v python3 >/dev/null || apt-get install -y python3
command -v smartctl >/dev/null || apt-get install -y smartmontools

id "$USER_NAME" >/dev/null 2>&1 || useradd --system --home-dir /srv/restic --shell /usr/sbin/nologin "$USER_NAME"
usermod -aG dialout "$USER_NAME"

install -d -m 755 /opt/bitrone-box /etc/bitrone-box
install -m 755 "$HERE/status/bitrone_box_status.py" /opt/bitrone-box/bitrone_box_status.py
if [ ! -f /etc/bitrone-box/box.conf ]; then
  install -m 644 "$HERE/status/box.conf.example" /etc/bitrone-box/box.conf
  [ -n "$DEVICE" ] && sed -i "s|^SMART_DEVICE=.*|SMART_DEVICE=$DEVICE|" /etc/bitrone-box/box.conf
  echo ">> создан /etc/bitrone-box/box.conf — впишите SN, CLIENT, SOURCE"
fi

sed "s/@USER@/$USER_NAME/g" "$HERE/status/bitrone-box-status.service" > /etc/systemd/system/bitrone-box-status.service

# SMART проверяет root раз в час и пишет итог в файл для службы экрана
cat > /etc/systemd/system/bitrone-box-smart.service <<'EOF'
[Unit]
Description=Bitrone Box SMART check

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'D=$$(sed -n "s/^SMART_DEVICE=//p" /etc/bitrone-box/box.conf); [ -n "$$D" ] || exit 0; install -d /var/lib/bitrone-box; smartctl -H "$$D" > /var/lib/bitrone-box/smart.txt.tmp 2>&1; mv /var/lib/bitrone-box/smart.txt.tmp /var/lib/bitrone-box/smart.txt; chmod 644 /var/lib/bitrone-box/smart.txt'
EOF
cat > /etc/systemd/system/bitrone-box-smart.timer <<'EOF'
[Unit]
Description=Bitrone Box SMART check (hourly)

[Timer]
OnBootSec=2min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now bitrone-box-smart.timer
systemctl enable --now bitrone-box-status.service
systemctl restart bitrone-box-status.service

echo
echo "Готово. Проверка:"
echo "  sudo -u $USER_NAME python3 /opt/bitrone-box/bitrone_box_status.py --once"
echo "  journalctl -u bitrone-box-status -f"
