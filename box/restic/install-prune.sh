#!/usr/bin/env bash
# Bitrone Box — установка очистки копий: restic client + prune-repos + systemd timer.
# Запуск на коробке:  sudo bash install-prune.sh
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[*] restic client"
if ! command -v restic >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq restic
fi
restic version || true

echo "[*] скрипт очистки → /usr/local/bin/bitrone-box-prune"
install -m 0755 "$HERE/prune-repos.sh" /usr/local/bin/bitrone-box-prune

mkdir -p /etc/bitrone-box/repos; chmod 750 /etc/bitrone-box/repos
mkdir -p /var/log/bitrone-box
if id restic >/dev/null 2>&1; then
  chown restic:restic /etc/bitrone-box/repos /var/log/bitrone-box
fi

cat >/etc/systemd/system/bitrone-box-prune.service <<'EOF'
[Unit]
Description=Bitrone Box — очистка старых копий restic
After=bitrone-rest-server.service

[Service]
Type=oneshot
User=restic
Group=restic
ExecStart=/usr/local/bin/bitrone-box-prune
EOF

cat >/etc/systemd/system/bitrone-box-prune.timer <<'EOF'
[Unit]
Description=Bitrone Box — ежедневная очистка копий

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now bitrone-box-prune.timer

echo
echo "================ очистка установлена ================"
echo "Таймер (ежедневно 03:30):"
systemctl list-timers bitrone-box-prune.timer --no-pager 2>/dev/null | head -n 2 || true
echo
echo "ПЕРЕД первым запуском — сохрани пароли репозиториев:"
echo "  sudo bash $HERE/save-repo-pass.sh <ИмяСервера>"
echo "Проверить вручную:   sudo systemctl start bitrone-box-prune.service"
echo "Лог:                 /var/log/bitrone-box/prune.log"
echo "Политику хранения менять в /etc/bitrone-box/prune.conf (KEEP_DAILY/WEEKLY/MONTHLY)"
echo "===================================================="
