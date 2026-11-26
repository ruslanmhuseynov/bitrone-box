# BitroneBackupSetup.exe — сборка

Мастер установки для сервера клиента: спрашивает **адрес коробки / папку / время**,
встраивает `restic.exe`, ставит файлы в `C:\Program Files\Bitrone`, создаёт ежедневную
задачу и делает тестовую копию. Пароль репозитория пишется в
`C:\ProgramData\Bitrone\box-enroll.txt` (открывается в конце) — его нужно сохранить на коробке.

## Собрать заново
1. Скачать restic для Windows (amd64) и положить сюда как `restic.exe`:
   https://github.com/restic/restic/releases → `restic_<ver>_windows_amd64.zip`
2. Скомпилировать:
   ```
   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" BitroneBackup.iss
   ```
   Результат — `Output\BitroneBackupSetup.exe`.

`restic.exe` и `Output\` в git не хранятся (см. .gitignore).

## Подпись (опционально)
Неподписанный .exe даёт предупреждение SmartScreen. Для снятия — code-signing сертификат:
`signtool sign /fd SHA256 /a Output\BitroneBackupSetup.exe`.
