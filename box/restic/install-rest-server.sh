#!/usr/bin/env bash
# Bitrone Box — установка rest-server (приёмник restic-копий, append-only).
#
# Поднимает на коробке HTTP-приёмник restic: клиентские серверы пушат сюда копии,
# но УДАЛЯТЬ их не могут (--append-only) — защита от шифровальщика, который пытается
# стереть бэкапы. Копии ложатся в <data>/<ИмяСервера>/ — ровно туда, где их ищет
# витрина (bitrone_box_status.find_repos).
#
# Запуск на коробке:
#   sudo bash install-rest-server.sh [--port 8000] [--user bitrone] [--data /srv/restic]
set -euo pipefail

VERSION="0.13.0"          # версия restic/rest-server (пин)
PORT=8000
HTUSER="bitrone"          # HTTP-логин для клиента
DATA="/srv/restic"        # где хранятся репозитории
SVCUSER="restic"          # системный пользователь службы

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --user) HTUSER="$2"; shift 2;;
    --data) DATA="$2"; shift 2;;
    *) echo "unknown arg: $1"; exit 1;;
  esac
done

[ "$(id -u)" = 0 ] || { echo "Запусти под root: sudo bash $0"; exit 1; }

case "$(uname -m)" in
  x86_64|amd64) ARCH=amd64;;
  i386|i686)    ARCH=386;;
  aarch64|arm64) ARCH=arm64;;
  armv7l|armv6l) ARCH=arm;;
  *) echo "Неизвестная архитектура: $(uname -m)"; exit 1;;
esac

echo "[*] Пакеты: curl, apache2-utils"
apt-get update -qq
apt-get install -y -qq curl apache2-utils

TARBALL="rest-server_${VERSION}_linux_${ARCH}.tar.gz"
URL="https://github.com/restic/rest-server/releases/download/v${VERSION}/${TARBALL}"
TMP="$(mktemp -d)"
echo "[*] Скачиваю $URL"
curl -fsSL "$URL" -o "$TMP/$TARBALL"
echo "[*] SHA256: $(sha256sum "$TMP/$TARBALL" | awk '{print $1}')"
echo "    (сверь с контрольной суммой на странице релиза GitHub)"
tar -xzf "$TMP/$TARBALL" -C "$TMP"
install -m 0755 "$TMP"/rest-server_*/rest-server /usr/local/bin/rest-server
rm -rf "$TMP"
/usr/local/bin/rest-server --version || true

id "$SVCUSER" >/dev/null 2>&1 || \
  useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin "$SVCUSER"
mkdir -p "$DATA"
chown -R "$SVCUSER:$SVCUSER" "$DATA"

CFGDIR="/etc/bitrone-box"
HTPASS="$CFGDIR/restic.htpasswd"
mkdir -p "$CFGDIR"
CREATED=0
if [ ! -f "$HTPASS" ]; then
  PW="$(head -c 15 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')"
  htpasswd -B -b -c "$HTPASS" "$HTUSER" "$PW"
  chown "$SVCUSER:$SVCUSER" "$HTPASS"; chmod 640 "$HTPASS"
  printf '%s\n' "$PW" > "$CFGDIR/restic.http.pass"
  chmod 600 "$CFGDIR/restic.http.pass"
  CREATED=1
fi

cat >/etc/systemd/system/bitrone-rest-server.service <<EOF
[Unit]
Description=Bitrone restic REST server (append-only)
After=network-online.target
Wants=network-online.target

[Service]
User=$SVCUSER
Group=$SVCUSER
ExecStart=/usr/local/bin/rest-server --path $DATA --listen :$PORT --append-only --htpasswd-file $HTPASS
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now bitrone-rest-server.service
sleep 1
systemctl --no-pager status bitrone-rest-server.service | head -n 6 || true

IP="$(hostname -I | awk '{print $1}')"
echo
echo "================ rest-server поднят ================"
echo "Данные:        $DATA"
echo "Порт:          $PORT   (открой в firewall, если включён)"
echo "append-only:   ВКЛ — клиент пишет копии, но не может их удалять"
echo
echo "URL репозитория для клиента (подставь ИмяСервера):"
echo "  rest:http://$HTUSER:<HTTP_PASS>@$IP:$PORT/<ИмяСервера>"
if [ "$CREATED" = 1 ]; then
  echo
  echo "HTTP-логин:    $HTUSER"
  echo "HTTP-пароль:   $(cat "$CFGDIR/restic.http.pass")"
  echo "               (сохранён в $CFGDIR/restic.http.pass)"
fi
echo
echo "Очистку старых копий (restic forget --prune) запускать НА КОРОБКЕ"
echo "отдельно (append-only блокирует удаление с клиента) — см. box/restic/README.md"
echo "==================================================="
