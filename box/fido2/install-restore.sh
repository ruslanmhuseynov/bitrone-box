#!/usr/bin/env bash
# Bitrone Box — установка восстановления с FIDO2 (pam_u2f, скрипты, тач-лаунчер).
# Запуск на коробке:  sudo bash box/fido2/install-restore.sh
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
BOX="$(cd "$HERE/.." && pwd)"

echo "[*] пакеты: libpam-u2f, pamtester, restic, python3-tk"
apt-get update -qq
apt-get install -y -qq libpam-u2f pamtester restic python3-tk

echo "[*] обновляю restic (нужна свежая версия для прогресса восстановления)"
restic self-update >/dev/null 2>&1 && restic version || echo "    (self-update не удался — прогресс может не отображаться, но восстановление работает)"

install -d -m 755 /opt/bitrone-box /srv/restore /var/log/bitrone-box
install -m 0755 "$BOX/restic/restore.sh"  /opt/bitrone-box/restore.sh
install -m 0755 "$HERE/restore-gui.py"    /opt/bitrone-box/restore-gui.py
install -m 0755 "$BOX/share/web-share.py" /opt/bitrone-box/web-share.py

echo "[*] PAM-сервис bitrone-restore (только касание ключа)"
cat >/etc/pam.d/bitrone-restore <<'EOF'
auth     required pam_u2f.so authfile=/etc/bitrone-box/u2f_keys origin=pam://bitrone appid=pam://bitrone cue
auth     required pam_permit.so
account  required pam_permit.so
EOF

# если экран работает под обычным пользователем — разрешаем ему звать restore под root
# (настоящая авторизация — внутри, через FIDO2). Если sudo нет — витрина/лаунчер идут под root.
if command -v sudo >/dev/null 2>&1; then
  KIOSK="${SUDO_USER:-kiosk}"
  echo "[*] sudoers: $KIOSK → /opt/bitrone-box/restore.sh (NOPASSWD, FIDO2 внутри)"
  mkdir -p /etc/sudoers.d
  printf '%s ALL=(root) NOPASSWD: /opt/bitrone-box/restore.sh\n' "$KIOSK" > /etc/sudoers.d/bitrone-restore
  chmod 440 /etc/sudoers.d/bitrone-restore
  visudo -cf /etc/sudoers.d/bitrone-restore >/dev/null
else
  echo "[*] sudo не установлен — пропускаю sudoers (витрина/лаунчер должны идти под root)."
fi

echo
echo "================ восстановление установлено ================"
echo "1) Зарегистрируй ключ:   sudo bash $HERE/enroll-fido2.sh"
echo "2) Проверь из консоли:   sudo /opt/bitrone-box/restore.sh <Сервер>"
echo "3) Тач-лаунчер на экране: python3 /opt/bitrone-box/restore-gui.py"
echo "   (как повесить на касание витрины — см. box/fido2/README.md)"
echo "Восстановленные файлы ложатся в /srv/restore/<Сервер>/"
echo "==========================================================="
