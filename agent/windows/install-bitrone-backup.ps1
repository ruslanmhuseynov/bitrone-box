# Bitrone Box — установщик агента на сервере клиента (бэкап + здоровье).
#
# Ставит restic, настраивает ежедневную отправку САМОГО СВЕЖЕГО файла из папки
# на коробку (restic append-only). Если задан -HealthToken — дополнительно
# ставит ежечасный сбор здоровья (collect-health.ps1 → коробка). Всё через задачи.
#
# Запуск (PowerShell ОТ АДМИНИСТРАТОРА на сервере клиента):
#   .\install-bitrone-backup.ps1
# или без вопросов:
#   .\install-bitrone-backup.ps1 -BoxUrl "rest:http://bitrone:PASS@192.168.0.50:8000" `
#        -Source "D:\1C\Backups" -Time "02:30"
#
# Указываем только 3 поля: адрес коробки, папку с бэкапами, время копирования.
# BoxUrl берётся из вывода install-rest-server.sh на коробке (содержит её IP).

param(
    [string]$BoxUrl,                 # rest:http://bitrone:PASS@<IP>:8000
    [string]$Source,                 # папка, откуда брать последний файл
    [string]$Time,                   # время ежедневного копирования, ЧЧ:ММ
    [string]$RepoPass = '',          # пароль шифрования; пусто → сгенерируем
    [string]$Mask = '*',             # необязательный фильтр файлов, напр. *.bak
    [string]$Server = $env:COMPUTERNAME,   # имя репозитория = имя сервера
    [string]$ResticExe = '',         # путь к restic.exe, если нет в интернете для winget
    [string]$HealthToken = '',       # токен приёмника health на коробке (пусто → health не настраивается)
    [int]$HealthPort = 8080,         # порт приёмника health на коробке
    [int]$HealthMinutes = 15         # отчёт о здоровье — каждые N минут
)

$ErrorActionPreference = 'Stop'
# нативные команды (restic, winget, вложенный powershell) не должны ронять установку по stderr
$PSNativeCommandUseErrorActionPreference = $false
$InstallDir = 'C:\Program Files\Bitrone'
$DataDir    = 'C:\ProgramData\Bitrone'
$TaskName   = 'BitroneBackup'

function Fail($m) { Write-Host "ОШИБКА: $m" -ForegroundColor Red; exit 1 }

# --- права администратора ---
$admin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Fail "запусти PowerShell от имени администратора" }

# --- спросить то, что не передали ---
if (-not $BoxUrl) { $BoxUrl = Read-Host "Адрес коробки (rest:http://bitrone:PASS@IP:8000)" }
if (-not $Source) { $Source = Read-Host "Папка с бэкапами (напр. D:\1C\Backups)" }
if (-not $Time)   { $Time   = Read-Host "Время копирования, ЧЧ:ММ (напр. 02:30)" }

if (-not $BoxUrl -or -not $Source -or -not $Time) { Fail "нужны адрес коробки, папка и время" }
if (-not (Test-Path -LiteralPath $Source)) { Fail "папка не найдена: $Source" }
try { $at = [datetime]::ParseExact($Time, 'HH:mm', $null) }
catch { Fail "время должно быть в формате ЧЧ:ММ, например 02:30" }

New-Item -ItemType Directory -Force -Path $InstallDir, $DataDir | Out-Null

# --- restic: проверить / поставить ---
function Have-Restic { try { & restic version *> $null; return ($LASTEXITCODE -eq 0) } catch { return $false } }
$resticPath = 'restic'
if ($ResticExe) {
    if (-not (Test-Path -LiteralPath $ResticExe)) { Fail "restic.exe не найден: $ResticExe" }
    $resticDest = Join-Path $InstallDir 'restic.exe'
    if ([IO.Path]::GetFullPath($ResticExe) -ne [IO.Path]::GetFullPath($resticDest)) {
        Copy-Item -LiteralPath $ResticExe -Destination $resticDest -Force
    }
    $resticPath = $resticDest
    Write-Host "restic: $resticDest"
} elseif (Have-Restic) {
    Write-Host "restic: уже установлен"
} else {
    Write-Host "restic не найден, ставлю через winget..."
    try { & winget install --id restic.restic -e --accept-source-agreements --accept-package-agreements 2>&1 | Out-Host } catch {}
    if (-not (Have-Restic)) {
        Fail "restic не установлен. Поставь вручную (winget install restic.restic) или запусти с -ResticExe C:\путь\restic.exe"
    }
    Write-Host "restic: установлен"
}

# --- пароль шифрования репозитория ---
if (-not $RepoPass) {
    $pool = (48..57) + (65..90) + (97..122)   # 0-9 A-Z a-z
    $RepoPass = -join ($pool | Get-Random -Count 24 | ForEach-Object { [char]$_ })
    Write-Host "пароль репозитория: сгенерирован"
}

# --- копируем рабочий скрипт рядом с установщиком ---
$srcScript = Join-Path $PSScriptRoot 'restic-backup.ps1'
if (-not (Test-Path -LiteralPath $srcScript)) { Fail "рядом нет restic-backup.ps1 ($srcScript)" }
$dstScript = Join-Path $InstallDir 'restic-backup.ps1'
if ([IO.Path]::GetFullPath($srcScript) -ne [IO.Path]::GetFullPath($dstScript)) {
    Copy-Item -LiteralPath $srcScript -Destination $dstScript -Force
}

# --- конфиг ---
$cfgPath = Join-Path $DataDir 'restic.conf'
$cfgLines = @(
    "BOX_URL=$BoxUrl",
    "SERVER=$Server",
    "RESTIC_PASSWORD=$RepoPass",
    "SOURCE=$Source",
    "MASK=$Mask"
)
if ($resticPath -ne 'restic') { $cfgLines += "RESTIC_EXE=$resticPath" }
Set-Content -Path $cfgPath -Value $cfgLines -Encoding utf8
# пароль в конфиге — скрыть от обычных пользователей
try {
    icacls $cfgPath /inheritance:r /grant:r "SYSTEM:(F)" "Administrators:(F)" *> $null
} catch {}
Write-Host "конфиг: $cfgPath"

# --- задача в планировщике: ежедневно в заданное время, от SYSTEM ---
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$dstScript`""
$trigger   = New-ScheduledTaskTrigger -Daily -At $at
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "задача '$TaskName': ежедневно в $Time"

# --- тестовый прогон ---
Write-Host "`nтестовая копия..."
& powershell.exe -NonInteractive -ExecutionPolicy Bypass -File $dstScript
$ok = ($LASTEXITCODE -eq 0)

# --- здоровье (health): collect-health.ps1 + health.conf + ежечасная задача ---
$healthLine = 'не настраивалось (токен не задан)'
if ($HealthToken) {
    $ip = $null
    if ($BoxUrl -match '@([^:@/]+):\d+') { $ip = $Matches[1] }
    if (-not $ip) {
        $healthLine = 'ПРОПУЩЕНО: не удалось определить IP коробки из адреса'
    } else {
        $healthUrl = "http://${ip}:$HealthPort"
        $srcH = Join-Path $PSScriptRoot 'collect-health.ps1'
        if (-not (Test-Path -LiteralPath $srcH)) { Fail "рядом нет collect-health.ps1 ($srcH)" }
        $dstH = Join-Path $InstallDir 'collect-health.ps1'
        if ([IO.Path]::GetFullPath($srcH) -ne [IO.Path]::GetFullPath($dstH)) {
            Copy-Item -LiteralPath $srcH -Destination $dstH -Force
        }
        $hcfg = Join-Path $DataDir 'health.conf'
        Set-Content -Path $hcfg -Value @("HEALTH_URL=$healthUrl", "HEALTH_TOKEN=$HealthToken") -Encoding utf8
        try { icacls $hcfg /inheritance:r /grant:r "SYSTEM:(F)" "Administrators:(F)" *> $null } catch {}
        $ha = New-ScheduledTaskAction -Execute 'powershell.exe' `
            -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$dstH`""
        if ($HealthMinutes -lt 1) { $HealthMinutes = 15 }
        $ht = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes $HealthMinutes)
        $hp = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
        $hs = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
        Register-ScheduledTask -TaskName 'BitroneHealth' -Action $ha -Trigger $ht `
            -Principal $hp -Settings $hs -Force | Out-Null
        Write-Host "задача 'BitroneHealth': каждые $HealthMinutes мин → $healthUrl"
        & powershell.exe -NonInteractive -ExecutionPolicy Bypass -File $dstH
        $healthLine = if ($LASTEXITCODE -eq 0) { "OK -> $healthUrl (каждые $HealthMinutes мин)" }
                      else { "задача создана, тест с ошибкой (см. collect-health.log)" }
    }
    Write-Host "health: $healthLine"
}

# --- сводка: на экран И в файл (при тихой установке из мастера консоли не видно) ---
$testLine = if ($ok) { 'OK' } else { 'ОШИБКА — см. лог' }
$enroll = @"
Bitrone Box — данные установки ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))

Сервер (репозиторий): $Server
Коробка:              $BoxUrl
Папка:                $Source   (маска $Mask)
Время копирования:    ежедневно $Time
Тест копии:           $testLine
Здоровье (health):    $healthLine
Лог:                  $DataDir\restic-backup.log

ВАЖНО для Bitrone — сохранить на коробке (нужно для очистки и восстановления):
  /etc/bitrone-box/repos/$Server.pass  =  $RepoPass
"@
$enrollPath = Join-Path $DataDir 'box-enroll.txt'
Set-Content -Path $enrollPath -Value $enroll -Encoding utf8
try { icacls $enrollPath /inheritance:r /grant:r "SYSTEM:(F)" "Administrators:(F)" *> $null } catch {}

Write-Host ""
Write-Host "================ ГОТОВО ================"
Write-Host $enroll
Write-Host "Эти данные сохранены в: $enrollPath"
Write-Host "======================================="
