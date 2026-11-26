#!/usr/bin/env bash
# Bitrone Box — регистрация FIDO2-ключа для восстановления.
#
# Вставь ключ в коробку и запусти:
#   sudo bash enroll-fido2.sh          # первый (основной) ключ — ПЕРЕЗАПИШЕТ список
#   sudo bash enroll-fido2.sh --add    # добавить ещё один (напр. запасной)
# Когда ключ замигает — коснись его.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0"; exit 1; }

AUTHFILE=/etc/bitrone-box/u2f_keys
ORIGIN="pam://bitrone"

command -v pamu2fcfg >/dev/null 2>&1 || { echo "[*] ставлю libpam-u2f"; apt-get update -qq; apt-get install -y -qq libpam-u2f; }
mkdir -p /etc/bitrone-box

if [ "${1:-}" = "--add" ]; then
  [ -f "$AUTHFILE" ] || { echo "Сначала зарегистрируй основной ключ (без --add)"; exit 1; }
  echo "[*] Вставь ДОПОЛНИТЕЛЬНЫЙ ключ и коснись его..."
  add="$(pamu2fcfg -n -o "$ORIGIN" -i "$ORIGIN")"   # печатает ':credential' без имени
  [ -n "$add" ] || { echo "Ключ не считан"; exit 1; }
  sed -i "1 s|\$|${add}|" "$AUTHFILE"               # дописать к строке root
  echo "[*] дополнительный ключ добавлен"
else
  echo "[*] Вставь ОСНОВНОЙ ключ и коснись его..."
  pamu2fcfg -u root -o "$ORIGIN" -i "$ORIGIN" > "$AUTHFILE"
  echo "[*] основной ключ записан"
fi

chmod 600 "$AUTHFILE"
echo "Готово: $AUTHFILE"
echo "Проверить гейт:  sudo pamtester bitrone-restore root authenticate  (должно попросить касание)"
