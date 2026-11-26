# Bitrone SOC — резервная копия restic на Bitrone Box.
#
# По расписанию (Scheduled Task) находит САМЫЙ СВЕЖИЙ файл в указанной папке
# и отправляет его через restic на коробку. restic в режиме append-only:
# копии на коробке нельзя удалить/перезаписать (защита от шифровальщика),
# плюс дедупликация и история версий.
#
# Конфиг (ключ=значение):  C:\ProgramData\Bitrone\restic.conf
#   BOX_URL=rest:http://bitrone:HTTP_PASS@192.168.0.XX:8000
#   SERVER=SERVER1C                                   # имя репо = имя сервера
#   RESTIC_PASSWORD=<пароль ШИФРОВАНИЯ репозитория>   # копия хранится у Bitrone (на коробке)
#   SOURCE=D:\1C\Backups                              # папка, откуда брать последний файл
#   MASK=*.bak                                        # необязательно: фильтр файлов (по умолчанию *)
#   RESTIC_EXE=C:\Program Files\restic\restic.exe     # необязательно, иначе ищем в PATH
#
# Установка — install-bitrone-backup.ps1 (ставит restic, пишет конфиг, создаёт задачу).

$ErrorActionPreference = 'Stop'
# restic-команды проверяем по кодам возврата; их stderr/ненулевой выход не должен ронять скрипт
$PSNativeCommandUseErrorActionPreference = $false
$cfgPath = 'C:\ProgramData\Bitrone\restic.conf'
$logPath = 'C:\ProgramData\Bitrone\restic-backup.log'
New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null

function Log([string]$m) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $logPath -Value "$ts $m" -Encoding utf8
}

if (-not (Test-Path $cfgPath)) { Log "НЕТ конфига $cfgPath"; throw "config missing" }
$cfg = @{}
foreach ($line in Get-Content $cfgPath) {
    $line = $line.Trim()
    if (-not $line -or $line.StartsWith('#') -or ($line -notmatch '=')) { continue }
    $k, $v = $line.Split('=', 2)
    $cfg[$k.Trim()] = $v.Trim()
}

$restic = if ($cfg.RESTIC_EXE -and (Test-Path $cfg.RESTIC_EXE)) { $cfg.RESTIC_EXE } else { 'restic' }
$server = $cfg.SERVER
$source = $cfg.SOURCE
$mask   = if ($cfg.MASK) { $cfg.MASK } else { '*' }

if (-not $server -or -not $cfg.BOX_URL -or -not $cfg.RESTIC_PASSWORD -or -not $source) {
    Log "Неполный конфиг (нужны SERVER/BOX_URL/RESTIC_PASSWORD/SOURCE)"; throw "bad config"
}
if (-not (Test-Path -LiteralPath $source)) { Log "НЕТ папки $source"; throw "source missing" }

# самый свежий файл в папке (по времени изменения)
$latest = Get-ChildItem -LiteralPath $source -File -Filter $mask -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { Log "В папке $source нет файлов по маске '$mask'"; exit 1 }

$env:RESTIC_REPOSITORY = "$($cfg.BOX_URL)/$server"
$env:RESTIC_PASSWORD   = $cfg.RESTIC_PASSWORD

# дальше нативный restic — ошибки ловим по кодам возврата, не по stderr
$ErrorActionPreference = 'Continue'

# репозиторий ещё не создан? (append-only позволяет init — создаёт новые файлы)
& $restic cat config *> $null
if ($LASTEXITCODE -ne 0) {
    Log "init репозитория $server"
    & $restic init 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) { Log "init FAILED"; throw "restic init failed" }
}

$sizeMb = [math]::Round($latest.Length / 1MB)
Log ("последний файл: {0}  ({1}, {2} МБ)" -f $latest.Name, $latest.LastWriteTime.ToString('yyyy-MM-dd HH:mm'), $sizeMb)
& $restic backup $latest.FullName --tag scheduled --host $server 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -eq 0) { Log "OK" } else { Log "backup FAILED ($LASTEXITCODE)"; exit 1 }

# Очистку (forget/prune) делает КОРОБКА — на клиенте append-only запрещает удаление.
