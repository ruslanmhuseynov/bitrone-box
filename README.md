# Bitrone Box

Автономное устройство в серверной клиента: неудаляемые бэкапы (restic append-only)
плюс витрина здоровья серверов на моноблоке. Отдельный продукт, с кабинетом SOC не связан.

## Структура
- `box/status/`  — витрина (tkinter) + сборка статуса из restic/health
- `box/restic/`  — приёмник rest-server (append-only) + очистка на коробке
- `box/enclosure`, `box/stand`, `box/stickers`, `box/firmware` — корпус / подставка / прошивки
- `box/rfq/`     — RFQ на корпус
- `agent/windows/` — клиент: install-bitrone-backup.ps1 + restic-backup.ps1 (последний файл → коробка)
- `marketing/`   — листовки (возможности, оффер)

## Быстрый старт
Коробка: `sudo bash box/restic/install-rest-server.sh`, затем служба витрины (`box/install-status.sh`).
Сервер клиента: `agent/windows/install-bitrone-backup.ps1` (IP коробки / папка / время).

Подробнее — `box/README.md` и `box/restic/README.md`.
