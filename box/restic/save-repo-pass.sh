#!/usr/bin/env bash
# Bitrone Box — сохранить пароль шифрования репозитория на коробке.
# Нужен для очистки (prune-repos.sh) и восстановления (клиент их делать не может).
#
# Использование:
#   sudo bash save-repo-pass.sh <ИмяСервера> [пароль]
# Без пароля — спросит скрытно (не отображая ввод).
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0 <Server> [pass]"; exit 1; }

name="${1:-}"
[ -n "$name" ] || { echo "Укажи имя сервера (= имя репозитория): sudo bash $0 <Server>"; exit 1; }

pass="${2:-}"
if [ -z "$pass" ]; then
  read -rsp "Пароль репозитория для $name: " pass; echo
fi
[ -n "$pass" ] || { echo "Пустой пароль — отмена"; exit 1; }

dir="/etc/bitrone-box/repos"
mkdir -p "$dir"; chmod 750 "$dir"
# без завершающего перевода строки — пароль должен совпадать с клиентским побайтово
printf '%s' "$pass" > "$dir/$name.pass"
chmod 600 "$dir/$name.pass"
if id restic >/dev/null 2>&1; then chown restic:restic "$dir" "$dir/$name.pass"; fi

echo "Сохранено: $dir/$name.pass"
