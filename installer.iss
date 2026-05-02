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
#define MyAppVersion     "1.0.0"
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

[Files]
; Everything PyInstaller produced
Source: "dist\Clicky\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}";                    Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";          Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}";              Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
; Offer to launch Clicky after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
{ Warn the user that a .env file is needed for the best experience }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not FileExists(ExpandConstant('{app}\.env')) then
    begin
      MsgBox(
        'Clicky installed successfully!' #13#13
        'To use paid AI providers (Claude, OpenAI, Gemini, ElevenLabs),' #13
        'create a file called .env inside:' #13#13
        '   ' + ExpandConstant('{app}') + #13#13
        'See .env.example for the template.' #13#13
        'Without keys, Clicky falls back to free Ollama + Whisper + Edge TTS.',
        mbInformation, MB_OK
      );
    end;
  end;
end;
