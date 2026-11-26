#!/usr/bin/env bash
# Bitrone Box — очистка старых копий restic НА КОРОБКЕ.
#
# Клиент пишет в append-only и удалять копии не может, поэтому retention
# (forget + prune) выполняет коробка — у неё есть доступ к ФС и пароли репо.
#
# Для каждого репозитория в /srv/restic берёт пароль из
# /etc/bitrone-box/repos/<ИмяРепо>.pass и применяет политику хранения.
# Репозитории без файла пароля пропускаются (с записью в лог).
set -uo pipefail

DATA="${BITRONE_REPO_ROOT:-/srv/restic}"
PASSDIR="/etc/bitrone-box/repos"
LOG="/var/log/bitrone-box/prune.log"

# политика хранения (можно переопределить в /etc/bitrone-box/prune.conf)
KEEP_DAILY=14
KEEP_WEEKLY=8
KEEP_MONTHLY=12
[ -f /etc/bitrone-box/prune.conf ] && . /etc/bitrone-box/prune.conf

mkdir -p "$(dirname "$LOG")"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

command -v restic >/dev/null 2>&1 || { log "ОШИБКА: restic не установлен"; exit 1; }

shopt -s nullglob
rc=0
found=0
for repo in "$DATA"/*/; do
  [ -f "${repo}config" ] || continue            # не репозиторий restic
  found=1
  name="$(basename "$repo")"
  pass="$PASSDIR/$name.pass"
  if [ ! -f "$pass" ]; then
    log "ПРОПУСК $name: нет файла пароля $pass"
    continue
  fi
  export RESTIC_REPOSITORY="$repo"
  export RESTIC_PASSWORD_FILE="$pass"
  log "=== $name: forget --prune (daily=$KEEP_DAILY weekly=$KEEP_WEEKLY monthly=$KEEP_MONTHLY) ==="
  if restic forget \
        --keep-daily "$KEEP_DAILY" --keep-weekly "$KEEP_WEEKLY" --keep-monthly "$KEEP_MONTHLY" \
        --group-by host --prune 2>&1 | tee -a "$LOG"; then
    log "$name: OK"
  else
    log "$name: ОШИБКА"; rc=1
  fi
  unset RESTIC_REPOSITORY RESTIC_PASSWORD_FILE
done
[ "$found" = 1 ] || log "репозиториев в $DATA не найдено"
exit $rc
