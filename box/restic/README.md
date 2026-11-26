# Bitrone Box — restic (бэкап у клиента)

Копии клиента остаются **локально на коробке**, append-only (клиент не может их удалить —
защита от шифровальщика). Витрина читает папки репозиториев и показывает свежесть копий.

```
Сервер клиента ──restic backup──▶ Bitrone Box : rest-server (append-only)
 (последний файл из папки,          /srv/restic/<Server>/     → витрина
  ежедневно по расписанию)
```

Копируется только **самый свежий файл** из указанной папки (например последний дамп
1С/SQL). restic дедуплицирует и держит историю; клиент удалять копии не может.

## 1. Коробка — приёмник (один раз)
```bash
sudo bash box/restic/install-rest-server.sh
```
Выведет URL, HTTP-логин/пароль. Пароль также в `/etc/bitrone-box/restic.http.pass`.
Этот URL (`rest:http://bitrone:PASS@<IP>:8000`) понадобится установщику на сервере.

## 2. Сервер клиента — отправитель (один раз)
Положить рядом `install-bitrone-backup.ps1` и `restic-backup.ps1`, запустить PowerShell
**от администратора**. Указываем только 3 поля — адрес коробки, папку, время:
```powershell
.\install-bitrone-backup.ps1 -BoxUrl "rest:http://bitrone:PASS@192.168.0.50:8000" `
    -Source "D:\1C\Backups" -Time "02:30"
```
Можно запустить без параметров — спросит их интерактивно. Установщик сам ставит restic,
пишет конфиг, создаёт задачу, делает тестовую копию и **печатает пароль репозитория** —
его нужно сохранить на коробке (см. ниже). Имя репозитория = имя сервера (`%COMPUTERNAME%`).

Необязательно: `-Mask "*.bak"` — фильтр файлов, `-Server ИМЯ` — другое имя репо.

## 3. Очистка старых копий — НА КОРОБКЕ (один раз)
append-only не даёт клиенту удалять, поэтому retention запускает коробка.
```bash
sudo bash box/restic/install-prune.sh                 # restic client + systemd-таймер (ежедневно 03:30)
sudo bash box/restic/save-repo-pass.sh <ИмяСервера>   # пароль репо — его печатает установщик на сервере
```
`prune-repos.sh` проходит по всем репозиториям в `/srv/restic`, берёт пароль из
`/etc/bitrone-box/repos/<ИмяРепо>.pass` и делает `forget --prune`. Репо без пароля
пропускаются. Политика хранения — в `/etc/bitrone-box/prune.conf`
(`KEEP_DAILY`/`KEEP_WEEKLY`/`KEEP_MONTHLY`, по умолчанию 14/8/12).

Проверить вручную: `sudo systemctl start bitrone-box-prune.service` · лог `/var/log/bitrone-box/prune.log`.

## Проверка
```bash
ls -la /srv/restic/              # появилась папка <Server> с config и snapshots/
sudo -u restic python3 /opt/bitrone-box/bitrone_box_status.py --once   # что уйдёт на экран
```
