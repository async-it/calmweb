#define MyAppName "CalmWeb"
; Version is injected by build.cmd via /DMyAppVersion=X.Y.Z
; Fallback for manual compilation:
#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Async IT Sàrl"
#define MyAppURL "https://github.com/async-it/calmweb"
#define MyAppExeName "calmweb.exe"

[Setup]
AppId={{972FD214-5A8A-4D95-9867-73ACAE1FFA63}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoTextVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright={#MyAppPublisher}
AppPublisher={#MyAppPublisher}
AppCopyright={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile=..\LICENSE
InfoBeforeFile=info_before_install.txt
InfoAfterFile=info_after_install.txt
OutputDir=..\dist
OutputBaseFilename=CalmWeb_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern
WizardImageFile=wizard.bmp
WizardSmallImageFile=wizard_small.bmp
SetupIconFile=..\resources\calmweb.ico
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName},0
UninstallFilesDir={app}\Uninstall
CloseApplications=force
CloseApplicationsFilter=calmweb.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\calmweb_installer.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
Source: "..\resources\calmweb_icon.png"; DestDir: "{app}"; DestName: "calmweb.png"; Flags: ignoreversion
Source: "..\resources\calmweb_active.png"; DestDir: "{app}"; DestName: "calmweb_active.png"; Flags: ignoreversion
Source: "scheduled_task.xml"; DestDir: "{app}"; Flags: ignoreversion; AfterInstall: PatchScheduledTaskXml

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{app}\Uninstall\unins000.exe"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
; Add firewall rule
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=CalmWeb dir=in action=allow program=""{app}\{#MyAppExeName}"" profile=any"; Flags: runhidden
; Create scheduled task
Filename: "schtasks"; Parameters: "/Create /tn CalmWeb /XML ""{app}\scheduled_task.xml"" /F"; Flags: runhidden
; Launch after install (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill running instances
Filename: "taskkill"; Parameters: "/IM calmweb.exe /F"; Flags: runhidden; RunOnceId: "KillCalmWeb"
; Remove firewall rule
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=CalmWeb"; Flags: runhidden; RunOnceId: "RemoveFirewallRule"
; Delete scheduled task
Filename: "schtasks"; Parameters: "/Delete /tn CalmWeb /F"; Flags: runhidden; RunOnceId: "DeleteScheduledTask"
; Reset system proxy
Filename: "netsh"; Parameters: "winhttp reset proxy"; Flags: runhidden; RunOnceId: "ResetWinHttpProxy"

[UninstallDelete]
Type: files; Name: "{userappdata}\CalmWeb\calmweb.lock"

[Code]
procedure PatchScheduledTaskXml();
var
  FilePath: String;
  FileContent: AnsiString;
  NewContent: String;
begin
  FilePath := ExpandConstant('{app}\scheduled_task.xml');
  if LoadStringFromFile(FilePath, FileContent) then
  begin
    NewContent := String(FileContent);
    StringChangeEx(NewContent, '__INSTALL_DIR__', ExpandConstant('{app}'), True);
    SaveStringToFile(FilePath, AnsiString(NewContent), False);
  end;
end;

procedure InitializeWizard();
begin
  WizardForm.BringToFront;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Reset proxy registry settings }
    RegWriteDWordValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Internet Settings', 'ProxyEnable', 0);
    RegWriteStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Internet Settings', 'ProxyServer', '');
  end;
end;
