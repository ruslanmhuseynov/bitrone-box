#!/usr/bin/env bash
# Bitrone Box — мастер установки «под ключ».
# Пишет /etc/bitrone-box/box.conf и поднимает все службы одной командой.
#
# Запуск на коробке (скопировав папку box/):
#   sudo bash box/install-box.sh
# или без вопросов:
#   sudo bash box/install-box.sh --sn BX-0001 --client INCHMARK --lang az
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

SN=""; CLIENT=""; LANG_=""; DEVICE="/dev/sda"
while [ $# -gt 0 ]; do
  case "$1" in
    --sn) SN="$2"; shift 2;;
    --client) CLIENT="$2"; shift 2;;
    --lang) LANG_="$2"; shift 2;;
    --device) DEVICE="$2"; shift 2;;
    *) echo "неизвестный аргумент: $1"; exit 1;;
  esac
done

[ -n "$SN" ]     || read -rp "Серийный номер коробки (напр. BX-0001): " SN
[ -n "$CLIENT" ] || read -rp "Клиент (короткое имя, напр. INCHMARK): " CLIENT
[ -n "$LANG_" ]  || { read -rp "Язык экрана az/ru/en [az]: " LANG_; LANG_="${LANG_:-az}"; }

CFG=/etc/bitrone-box/box.conf
mkdir -p /etc/bitrone-box
if [ ! -f "$CFG" ]; then
  cat > "$CFG" <<EOF
# /etc/bitrone-box/box.conf — Bitrone Box
REPO_ROOT=/srv/restic
HEALTH_ROOT=/srv/bitrone/health
HEALTH_PORT=8080

SN=$SN
CLIENT=$CLIENT
SOURCE=

LANG=$LANG_

WARN_HOURS=2
FULL_WARN_DAYS=8
DISK_WARN_PCT=85
SMART_DEVICE=$DEVICE

SERIAL=auto
CONTRAST=90
INTERVAL=10
EOF
  echo "[*] создан $CFG  (SN=$SN  CLIENT=$CLIENT)"
else
  echo "[*] $CFG уже существует — оставляю как есть"
fi

echo; echo "===== 1/4 приёмник копий (restic rest-server) ====="
bash "$HERE/restic/install-rest-server.sh"
echo; echo "===== 2/4 приёмник health ====="
bash "$HERE/health/install-health-receiver.sh"
echo; echo "===== 3/4 очистка копий (prune) ====="
bash "$HERE/restic/install-prune.sh"
echo; echo "===== 4/4 витрина (экран) ====="
bash "$HERE/install-status.sh"

# ---- финальная сводка для сервера клиента ----
IP="$(hostname -I | awk '{print $1}')"
HPASS="$(cat /etc/bitrone-box/restic.http.pass 2>/dev/null || echo '<см. вывод шага 1>')"
HTOKEN="$(grep -E '^HEALTH_TOKEN=' "$CFG" 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
HPORT="$(grep -E '^HEALTH_PORT=' "$CFG" 2>/dev/null | tail -n1 | cut -d= -f2- || true)"

cat <<EOF

================= КОРОБКА ГОТОВА =================
IP коробки:  $IP

Вбей это в установщик на сервере клиента (BitroneBackupSetup.exe):
  Адрес коробки:   rest:http://bitrone:$HPASS@$IP:8000
  Токен здоровья:  $HTOKEN
  (порт здоровья $HPORT — менять не нужно)

Не забудь сохранить пароль репозитория с сервера:
  sudo bash $HERE/restic/save-repo-pass.sh <ИмяСервера>
=================================================
EOF
