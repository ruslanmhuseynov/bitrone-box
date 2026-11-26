# Bitrone Box — восстановление с FIDO2

Восстановление копии требует **касания аппаратного ключа** (YubiKey и т.п.) через
`pam_u2f`. Запустить можно из консоли или **долгим касанием угла витрины**.

```
Экран (долгое касание угла) ──▶ restore-gui.py ──▶ sudo restore.sh <Сервер>
                                                      │ требует касания FIDO2-ключа (pam_u2f)
                                                      ▼
                                         restic restore latest → /srv/restore/<Сервер>/
```

## Установка (на коробке, один раз)
```bash
sudo bash box/fido2/install-restore.sh      # pam_u2f, pamtester, restic, python3-tk, PAM-сервис, sudoers
sudo bash box/fido2/enroll-fido2.sh         # вставь ключ, коснись — зарегистрирует
sudo bash box/fido2/enroll-fido2.sh --add   # (необязательно) запасной ключ
```
Проверка гейта: `sudo pamtester bitrone-restore root authenticate` — должно попросить касание.

## Как восстановить
- **Консоль:** `sudo /opt/bitrone-box/restore.sh <Сервер> [snapshot] [target]`
  (snapshot по умолчанию `latest`, target — `/srv/restore/<Сервер>`).
- **Экран:** нажми и удерживай **≥1.5 с правый верхний угол** витрины → откроется лаунчер →
  кнопка сервера → «Да» → приложи ключ. (Нужен обновлённый `bitrone_box_screen.py`.)

Восстановленные файлы: `/srv/restore/<Сервер>/…` (с исходной структурой путей).
Отдать на сервер: `pscp kiosk@<IP>:/srv/restore/<Сервер>/путь/файл.bak C:\Restore\`.

## Что это даёт и чего НЕ даёт (честно)
- ✅ Восстановление невозможно **без присутствия и касания** зарегистрированного ключа —
  второй фактор, защита от случайного/UI-доступа.
- ⚠️ Это **гейт авторизации**, а не крипто-замок на пароле репозитория: пароль по-прежнему
  лежит для ночной очистки в `/etc/bitrone-box/repos/<Сервер>.pass`, и пользователь с root
  на коробке может обойти гейт. Для защиты «даже root не расшифрует без ключа» нужно
  оборачивать пароль через FIDO2 **hmac-secret** (следующий уровень).

## Файлы
- `box/restic/restore.sh` — восстановление с FIDO2-гейтом
- `box/fido2/enroll-fido2.sh` — регистрация ключа(ей)
- `box/fido2/install-restore.sh` — pam_u2f + PAM-сервис + sudoers + копирование
- `box/fido2/restore-gui.py` — тач-лаунчер на витрине
- хук в `box/status/bitrone_box_screen.py` — долгое касание угла запускает лаунчер
