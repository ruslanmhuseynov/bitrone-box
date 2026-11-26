#!/usr/bin/env bash
# Bitrone Box — восстановление копии С ОБЯЗАТЕЛЬНЫМ касанием FIDO2-ключа.
#
# Перед расшифровкой требует подтверждения аппаратным ключом (pam_u2f).
# Использование:
#   sudo bash restore.sh <Сервер> [snapshot] [target]
# snapshot  — id снимка или latest (по умолчанию latest)
# target    — куда восстановить (по умолчанию /srv/restore/<Сервер>)
set -euo pipefail

PAM_SERVICE="bitrone-restore"
PAM_USER="root"
REPO_ROOT="/srv/restic"
PASSDIR="/etc/bitrone-box/repos"
RESTORE_ROOT="/srv/restore"
SHARE_PORT=8090            # временный веб-доступ для скачивания
SHARE_HOURS=3             # на сколько часов открыть
WEB_SHARE="/opt/bitrone-box/web-share.py"
LOGDIR="/var/log/bitrone-box"

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0 <Сервер>"; exit 1; }

server="${1:-}"
snap="${2:-latest}"
[ -n "$server" ] || { echo "Укажи сервер: sudo bash $0 <Сервер> [snapshot] [target]"; exit 1; }
target="${3:-$RESTORE_ROOT/$server}"

repo="$REPO_ROOT/$server"
pass="$PASSDIR/$server.pass"
[ -f "$repo/config" ] || { echo "Нет репозитория: $repo"; exit 1; }
[ -f "$pass" ]        || { echo "Нет пароля репо: $pass  (сделай save-repo-pass.sh $server)"; exit 1; }
command -v restic    >/dev/null || { echo "restic не установлен"; exit 1; }
command -v pamtester >/dev/null || { echo "pamtester не установлен — запусти box/fido2/install-restore.sh"; exit 1; }
[ -f /etc/bitrone-box/u2f_keys ] || { echo "Ключ не зарегистрирован — запусти box/fido2/enroll-fido2.sh"; exit 1; }

# сбросить прогресс в «ожидание ключа» (-1), затирая прошлый запуск
mkdir -p /run/bitrone-box
printf -- '-1\n' > /run/bitrone-box/restore.pct 2>/dev/null || true
chmod 644 /run/bitrone-box/restore.pct 2>/dev/null || true

echo ">> Приложите ключ Bitrone к коробке и коснитесь его..."
if ! pamtester "$PAM_SERVICE" "$PAM_USER" authenticate; then
  echo "ОТКАЗАНО: FIDO2-ключ не подтверждён. Восстановление отменено."
  exit 1
fi
echo ">> Ключ подтверждён. Восстанавливаю $server ($snap)..."
export RESTIC_REPOSITORY="$repo"
export RESTIC_PASSWORD_FILE="$pass"

# восстанавливаем во временную папку, затем кладём файлы ПЛОСКО в target
mkdir -p "$target" "$RESTORE_ROOT" /run/bitrone-box
tmp="${target}.restoring"
rm -rf "$tmp"; mkdir -p "$tmp"; chmod 755 "$tmp"
trap 'rm -rf "$tmp"' EXIT

# прогресс берём из самого restic (--json) — он точно знает, сколько восстановлено
# (du не годится: restic заранее резервирует весь размер файла). Пишем % в файл для лаунчера.
# Нужна restic >= ~0.17 (install-restore.sh делает self-update).
PCTFILE="/run/bitrone-box/restore.pct"
printf '0\n' > "$PCTFILE"; chmod 644 "$PCTFILE"
restic restore "$snap" --target "$tmp" --json | while IFS= read -r line; do
  case "$line" in
    *'"percent_done"'*)
      pd="${line##*\"percent_done\":}"; pd="${pd%%,*}"
      awk -v x="$pd" 'BEGIN{p=int(x*100); if(p>99)p=99; if(p<0)p=0; print p}' > "$PCTFILE" 2>/dev/null || true
      ;;
  esac
done
printf '100\n' > "$PCTFILE"

find "$tmp" -type f -exec mv -f {} "$target/" \;   # без дерева путей — просто файлы
rm -rf "$tmp"; trap - EXIT

echo
echo "Готово. Файлы здесь: $target"
find "$target" -maxdepth 1 -type f -printf '%f  (%s байт)\n' 2>/dev/null

# временный веб-доступ на N часов; потом доступ закроется и данные удалятся
if [ -f "$WEB_SHARE" ]; then
  mkdir -p "$LOGDIR"
  ip="$(hostname -I | awk '{print $1}')"
  pkill -f "web-share.py .* $SHARE_PORT " 2>/dev/null || true
  setsid python3 "$WEB_SHARE" "$target" "$SHARE_PORT" "$((SHARE_HOURS*3600))" "$target" \
      >"$LOGDIR/web-share.log" 2>&1 &
  sleep 1
  echo
  echo "Скачать можно $SHARE_HOURS ч с любого ПК в сети:"
  echo "  http://$ip:$SHARE_PORT/"
  echo "(список файлов; через $SHARE_HOURS ч доступ закроется и восстановленные данные удалятся)"
  echo "(порт $SHARE_PORT открой в firewall, если он включён)"
else
  echo "(web-share.py не установлен — перезапусти install-restore.sh для веб-доступа)"
fi
