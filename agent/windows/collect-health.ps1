# Bitrone Box — сбор «жизнедеятельности» сервера в health.json и отправка на коробку.
#
# ТОЛЬКО ЧТЕНИЕ: ничего на сервере не меняет. Каждый блок защищён try/catch,
# чтобы сбой одного датчика не ронял весь отчёт.
#
# Конфиг (необязательный):  C:\ProgramData\Bitrone\health.conf
#   HEALTH_URL=http://192.168.0.50:8080      # адрес приёмника на коробке
#   HEALTH_TOKEN=<токен>                     # его печатает install-health-receiver.sh
#   ROLE=1C serveri                          # необязательно: подпись сервера
# Без конфига отчёт просто пишется локально (C:\ProgramData\Bitrone\health.json).
#
# Запуск по расписанию (напр. раз в час) — см. конец файла.

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$DataDir  = 'C:\ProgramData\Bitrone'
$cfgPath  = Join-Path $DataDir 'health.conf'
$jsonPath = Join-Path $DataDir 'health.json'
$logPath  = Join-Path $DataDir 'collect-health.log'
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Log([string]$m) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $logPath -Value "$ts $m" -Encoding utf8
}
function Try1([scriptblock]$b, $default) { try { & $b } catch { $default } }

$cfg = @{}
if (Test-Path $cfgPath) {
    foreach ($line in Get-Content $cfgPath) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith('#') -or ($line -notmatch '=')) { continue }
        $k, $v = $line.Split('=', 2); $cfg[$k.Trim()] = $v.Trim()
    }
}

$name = $env:COMPUTERNAME
$now  = [int][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

# ---------- система ----------
$system = Try1 {
    $os  = Get-CimInstance Win32_OperatingSystem
    $ubr = Try1 { (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR } $null
    $boot = $os.LastBootUpTime
    [ordered]@{
        os          = ($os.Caption -replace '^Microsoft\s+', '').Trim()
        build       = if ($ubr) { "$($os.BuildNumber).$ubr" } else { "$($os.BuildNumber)" }
        uptime_days = [math]::Round(((Get-Date) - $boot).TotalDays, 2)
        last_boot   = [int][DateTimeOffset]::new($boot).ToUnixTimeSeconds()
    }
} $null

# ---------- стабильность (падения/WHEA за 24ч и 7д) ----------
$stability = Try1 {
    $cnt = {
        param($ids, $hours)
        Try1 {
            (Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = $ids
                StartTime = (Get-Date).AddHours(-$hours) } -ErrorAction Stop).Count
        } 0
    }
    $whea = Try1 {
        (Get-WinEvent -FilterHashtable @{ ProviderName = 'Microsoft-Windows-WHEA-Logger'
            StartTime = (Get-Date).AddHours(-24) } -ErrorAction Stop).Count
    } 0
    [ordered]@{
        crashes_24h = & $cnt @(41, 1001, 6008) 24
        crashes_7d  = & $cnt @(41, 1001, 6008) 168
        whea        = [int]$whea
        last_dump   = if (Test-Path 'C:\Windows\MEMORY.DMP') { 'MEMORY.DMP' } else { '' }
    }
} $null

# ---------- диски (SMART + тома) ----------
$disks = Try1 {
    $pd = Try1 { Get-PhysicalDisk -ErrorAction Stop } @()
    $smart = 'ok'
    foreach ($d in $pd) {
        switch ($d.HealthStatus) {
            'Unhealthy' { $smart = 'bad' }
            'Warning'   { if ($smart -ne 'bad') { $smart = 'warn' } }
        }
    }
    $temp = $null; $wear = $null
    foreach ($d in $pd) {
        $rc = Try1 { $d | Get-StorageReliabilityCounter -ErrorAction Stop } $null
        if ($rc) {
            if ($rc.Temperature -ne $null) { if ($temp -eq $null -or $rc.Temperature -gt $temp) { $temp = [int]$rc.Temperature } }
            if ($rc.Wear -ne $null)        { if ($wear -eq $null -or $rc.Wear -gt $wear)        { $wear = [int]$rc.Wear } }
        }
    }
    $vols = @()
    foreach ($v in (Try1 { Get-Volume -ErrorAction Stop } @())) {
        if ($v.DriveType -ne 'Fixed' -or -not $v.DriveLetter -or -not $v.Size) { continue }
        $o = [ordered]@{ vol = "$($v.DriveLetter)" }
        if ($v.FileSystemLabel) { $o.label = $v.FileSystemLabel }
        $o.free_pct = [int][math]::Round($v.SizeRemaining * 100 / $v.Size)
        $o.free_gb  = [int][math]::Round($v.SizeRemaining / 1GB)
        $vols += $o
    }
    [ordered]@{ smart = $smart; temp_c = $temp; wear_pct = $wear; volumes = $vols }
} $null

# ---------- память (ECC) ----------
$memory = Try1 {
    $cs = Get-CimInstance Win32_ComputerSystem
    $mods = Try1 { (Get-CimInstance Win32_PhysicalMemory).Count } $null
    $ecc = Try1 {
        switch ((Get-CimInstance Win32_PhysicalMemoryArray | Select-Object -First 1).MemoryErrorCorrection) {
            3 { 'none' } 4 { 'parity' } 5 { 'single-bit' } 6 { 'multi-bit' } 7 { 'crc' } default { 'unknown' }
        }
    } 'unknown'
    [ordered]@{ total_gb = [int][math]::Round($cs.TotalPhysicalMemory / 1GB); ecc = $ecc; modules = $mods }
} $null

# ---------- обновления ----------
$patching = Try1 {
    $pending = Try1 {
        (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') -or
        (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')
    } $false
    $auto = Try1 {
        $no = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue).NoAutoUpdate
        if ($no -eq 1) { 'off' } elseif ((Get-Service wuauserv -ErrorAction SilentlyContinue).StartType -eq 'Disabled') { 'off' } else { 'on' }
    } 'on'
    $pend = Try1 {
        $s = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
        $s.Online = $false
        [int]$s.Search('IsInstalled=0 and IsHidden=0').Updates.Count
    } $null
    [ordered]@{ pending_reboot = [bool]$pending; autoupdate = $auto; updates_pending = $pend }
} $null

# ---------- активация Windows ----------
$activation = Try1 {
    $p = Get-CimInstance SoftwareLicensingProduct -Filter "PartialProductKey IS NOT NULL AND ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f'" -ErrorAction Stop |
         Select-Object -First 1
    $st = switch ($p.LicenseStatus) { 1 { 'ok' } 5 { 'notification' } default { 'other' } }
    [ordered]@{ status = $st }
} $null

# ---------- RDP / терминал ----------
$rds = Try1 {
    $svc = Try1 { if ((Get-Service TermService -ErrorAction Stop).Status -eq 'Running') { 'running' } else { 'stopped' } } 'unknown'
    $sess = Try1 { @(quser 2>$null | Select-Object -Skip 1).Count } $null
    [ordered]@{ termservice = $svc; sessions_active = $sess }
} $null

# ---------- сборка ----------
$report = [ordered]@{
    name = $name; online = $true; updated = $now
    system = $system; stability = $stability; disks = $disks
    memory = $memory; patching = $patching; activation = $activation; rds = $rds
}
if ($cfg.ROLE) { $report.role = $cfg.ROLE }

$json = $report | ConvertTo-Json -Depth 6
Set-Content -Path $jsonPath -Value $json -Encoding utf8
Log "собрано: $jsonPath"

# ---------- отправка на коробку ----------
if ($cfg.HEALTH_URL -and $cfg.HEALTH_TOKEN) {
    try {
        $uri = $cfg.HEALTH_URL.TrimEnd('/') + '/health/' + $name
        Invoke-RestMethod -Uri $uri -Method Put -Body $json -ContentType 'application/json; charset=utf-8' `
            -Headers @{ Authorization = "Bearer $($cfg.HEALTH_TOKEN)" } -TimeoutSec 15 | Out-Null
        Log "отправлено на $uri"
    } catch {
        Log "ОШИБКА отправки на коробку: $($_.Exception.Message)"
    }
} else {
    Log "HEALTH_URL/HEALTH_TOKEN не заданы — только локальный файл"
}

# ============================================================================
# РАЗОВО (ежечасная задача, PowerShell от администратора):
#   $a = New-ScheduledTaskAction -Execute 'powershell.exe' `
#          -Argument '-NonInteractive -ExecutionPolicy Bypass -File "C:\Program Files\Bitrone\collect-health.ps1"'
#   $t = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)
#   $p = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
#   Register-ScheduledTask -TaskName 'BitroneHealth' -Action $a -Trigger $t -Principal $p -Force
# ============================================================================
