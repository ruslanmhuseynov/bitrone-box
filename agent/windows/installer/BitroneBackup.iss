; Bitrone Box — установщик резервного копирования для сервера клиента.
; Собрать:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" BitroneBackup.iss
; Результат: Output\BitroneBackupSetup.exe
;
; Мастер спрашивает: папку (с кнопкой Обзор), адрес коробки, расширение, время.
; Встраивает restic.exe, ставит файлы в C:\Program Files\Bitrone,
; запускает install-bitrone-backup.ps1.

#define AppName "Bitrone Backup"
#define AppVer  "1.0.0"

[Setup]
AppId={{B17E0B0C-BA11-4B0C-9E55-B170EBAC0DE1}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=Bitrone
DefaultDirName={autopf}\Bitrone
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=no
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=BitroneBackupSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Bitrone Backup

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "restic.exe";                       DestDir: "{app}"; Flags: ignoreversion
Source: "..\install-bitrone-backup.ps1";    DestDir: "{app}"; Flags: ignoreversion
Source: "..\restic-backup.ps1";             DestDir: "{app}"; Flags: ignoreversion
Source: "..\collect-health.ps1";            DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "powershell.exe"; \
  Parameters: "-NonInteractive -ExecutionPolicy Bypass -File ""{app}\install-bitrone-backup.ps1"" -BoxUrl ""{code:GetBoxUrl}"" -Source ""{code:GetSource}"" -Mask ""{code:GetMask}"" -Time ""{code:GetTime}"" -HealthToken ""{code:GetHealthToken}"" -HealthMinutes ""{code:GetHealthMinutes}"" -ResticExe ""{app}\restic.exe"""; \
  StatusMsg: "Настройка резервного копирования и первая тестовая копия..."; \
  Flags: runhidden waituntilterminated
Filename: "notepad.exe"; Parameters: "{commonappdata}\Bitrone\box-enroll.txt"; \
  Description: "Показать данные для коробки (пароль репозитория)"; \
  Flags: postinstall skipifsilent nowait

[UninstallRun]
Filename: "schtasks.exe"; Parameters: "/Delete /TN BitroneBackup /F"; Flags: runhidden; RunOnceId: "DelTask"

[Code]
var
  DirPage: TInputDirWizardPage;
  InputPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  DirPage := CreateInputDirPage(wpWelcome,
    'Папка с бэкапами',
    'Откуда брать последний файл для копирования.',
    'Выберите папку, куда сервер складывает бэкапы (дампы 1С / SQL и т.п.).',
    False, '');
  DirPage.Add('Папка с бэкапами:');

  InputPage := CreateInputQueryPage(DirPage.ID,
    'Подключение к Bitrone Box',
    'Параметры от Bitrone и что именно копировать.',
    'Эти данные даёт Bitrone при установке коробки.');
  InputPage.Add('Адрес коробки  (rest:http://bitrone:ПАРОЛЬ@IP:8000):', False);
  InputPage.Add('Расширение файлов  (например *.bak; пусто = все):', False);
  InputPage.Add('Время копирования БЭКАПА, ЧЧ:ММ  (раз в день, например 02:30):', False);
  InputPage.Add('Токен здоровья от коробки  (пусто — без мониторинга):', False);
  InputPage.Add('Отчёт о здоровье — каждые N минут  (например 15):', False);
  InputPage.Values[1] := '*.bak';
  InputPage.Values[2] := '02:30';
  InputPage.Values[4] := '15';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  boxUrl, src, tm: string;
begin
  Result := True;
  if CurPageID = DirPage.ID then
  begin
    src := Trim(DirPage.Values[0]);
    if src = '' then begin
      MsgBox('Укажите папку с бэкапами.', mbError, MB_OK); Result := False; Exit;
    end;
    if not DirExists(src) then begin
      MsgBox('Папка не найдена:' + #13#10 + src, mbError, MB_OK); Result := False; Exit;
    end;
  end
  else if CurPageID = InputPage.ID then
  begin
    boxUrl := Trim(InputPage.Values[0]);
    tm     := Trim(InputPage.Values[2]);
    if boxUrl = '' then begin
      MsgBox('Укажите адрес коробки.', mbError, MB_OK); Result := False; Exit;
    end;
    if Pos('rest:', boxUrl) <> 1 then begin
      MsgBox('Адрес должен начинаться с  rest:http://', mbError, MB_OK); Result := False; Exit;
    end;
    if (Length(tm) <> 5) or (tm[3] <> ':') then begin
      MsgBox('Время копирования — в формате ЧЧ:ММ, например 02:30', mbError, MB_OK); Result := False; Exit;
    end;
    if (Trim(InputPage.Values[3]) <> '') and (StrToIntDef(Trim(InputPage.Values[4]), 0) <= 0) then begin
      MsgBox('Отчёт о здоровье — целое число минут, например 15', mbError, MB_OK); Result := False; Exit;
    end;
  end;
end;

function GetBoxUrl(Param: string): string;
begin Result := Trim(InputPage.Values[0]); end;

function GetSource(Param: string): string;
begin Result := Trim(DirPage.Values[0]); end;

function GetMask(Param: string): string;
var
  m: string;
begin
  m := Trim(InputPage.Values[1]);
  if m = '' then
    m := '*'
  else if Pos('*', m) = 0 then
  begin
    if Copy(m, 1, 1) = '.' then m := '*' + m
    else m := '*.' + m;
  end;
  Result := m;
end;

function GetTime(Param: string): string;
begin Result := Trim(InputPage.Values[2]); end;

function GetHealthToken(Param: string): string;
begin Result := Trim(InputPage.Values[3]); end;

function GetHealthMinutes(Param: string): string;
var v: string;
begin
  v := Trim(InputPage.Values[4]);
  if v = '' then v := '15';
  Result := v;
end;
