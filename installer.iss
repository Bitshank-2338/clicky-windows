; ────────────────────────────────────────────────────────────────────
;  Clicky for Windows — Inno Setup script
;
;  Builds a single Setup-Clicky.exe from the PyInstaller dist folder.
;
;  Prerequisites:
;    1. Run  build.bat  first (produces dist\Clicky\)
;    2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
;    3. Run:  iscc installer.iss
;
;  Output:  dist\Setup-Clicky.exe   (single-file installer, ~200-400 MB)
; ────────────────────────────────────────────────────────────────────

#define MyAppName        "Clicky"
#define MyAppVersion     "1.1.1"
#define MyAppPublisher   "Shashank Singh"
#define MyAppURL         "https://github.com/Bitshank-2338/clicky-windows"
#define MyAppExeName     "Clicky.exe"

[Setup]
AppId={{9A4E3F2C-7B1D-4A8F-9C6E-3D7F1B5E9A0C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputDir=dist
OutputBaseFilename=Setup-Clicky
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
#if FileExists("assets\icon.ico")
  SetupIconFile=assets\icon.ico
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startupicon";  Description: "Launch Clicky when Windows &starts";  GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "installollama"; Description: "Also download && install Ollama (free local AI engine, ~700 MB) — needed for the no-API-key mode"; GroupDescription: "Free AI engine:"

[Files]
; Everything PyInstaller produced
Source: "dist\Clicky\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";                    Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";          Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Optional: download + run the official Ollama installer when the user opts in.
; PowerShell does the download (no extra tooling needed); the Ollama installer
; itself is an Inno Setup wizard so /SILENT works.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$ErrorActionPreference='Stop'; $url='https://ollama.com/download/OllamaSetup.exe'; $dst=Join-Path $env:TEMP 'OllamaSetup.exe'; Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing; Start-Process -FilePath $dst -ArgumentList '/SILENT' -Wait"""; \
  StatusMsg: "Downloading and installing Ollama (this can take a few minutes)..."; \
  Tasks: installollama; \
  Flags: runhidden waituntilterminated

; Offer to launch Clicky after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox(
      'Clicky installed successfully!' #13#13
      'On first launch, Clicky will walk you through downloading the AI models' #13
      'so it can answer your questions offline (free, no API keys needed).' #13#13
      'You can also use Claude / OpenAI / Gemini / GitHub Copilot — see' #13
      '.env.example inside the install folder for the template.',
      mbInformation, MB_OK
    );
  end;
end;
