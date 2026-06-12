; =============== QuizApp.iss ===============
; Inno Setup script for the packaged QuizApp build.
; Build flow:
;   1. Run install.bat to create dist\QuizApp.exe with PyInstaller.
;   2. Compile this script with Inno Setup, or let install.bat run ISCC.exe.

#define AppName        "QuizApp"
#define AppVersion     "1.0.4"
#define AppPublisher   "PPMG Ekarh Antim I"
#define AppURL         "https://pmg-vd.org"
#define ExeName        "QuizApp.exe"
#define DistDir        "dist"

[Setup]
AppId={{6E1C4A95-5C68-4B28-A6B7-D37D7D5B4F2C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={pf}\{#AppName}
DefaultGroupName={#AppName}
DisableDirPage=no
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#ExeName}
OutputDir=output
OutputBaseFilename=Setup_{#AppName}_{#AppVersion}
ChangesEnvironment=yes
WizardStyle=modern

[Languages]
Name: "bulgarian"; MessagesFile: "compiler:Languages\Bulgarian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "setenv"; Description: "Set the system QUIZ_ADMIN_PASS environment variable"; GroupDescription: "Optional settings:"; Flags: unchecked

[Dirs]
Name: "{app}\reports"; Permissions: users-modify; Flags: uninsalwaysuninstall
Name: "{app}\questions"; Permissions: users-modify; Flags: uninsalwaysuninstall
Name: "{app}\skins"; Permissions: users-modify; Flags: uninsalwaysuninstall
Name: "{app}\templates"; Permissions: users-modify; Flags: uninsalwaysuninstall
Name: "{app}\profiles"; Permissions: users-modify; Flags: uninsalwaysuninstall

[Files]
Source: "{#DistDir}\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "grading_scale.csv"; DestDir: "{app}"; Flags: ignoreversion
Source: "instructions.txt"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "instructions.docx"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "images\*"; DestDir: "{app}\images"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "sounds\*"; DestDir: "{app}\sounds"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "fonts\*"; DestDir: "{app}\fonts"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "skins\*"; DestDir: "{app}\skins"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "templates\*"; DestDir: "{app}\templates"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "questions\*"; DestDir: "{app}\questions"; Flags: recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Launch {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent skipifdoesntexist

[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "QUIZ_ADMIN_PASS"; ValueData: "{code:GetAdminPass}"; Flags: uninsdeletevalue; Tasks: setenv; Check: ShouldWriteAdminPass

[Code]
var
  EnvPage: TInputQueryWizardPage;

function GetAdminPass(Value: string): string;
begin
  Result := '';
  if Assigned(EnvPage) then
    Result := EnvPage.Values[0];
end;

function ShouldWriteAdminPass: Boolean;
begin
  Result := WizardIsTaskSelected('setenv') and Assigned(EnvPage) and (EnvPage.Values[0] <> '');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Assigned(EnvPage) and (PageID = EnvPage.ID) and (not WizardIsTaskSelected('setenv')) then
    Result := True;
end;

procedure InitializeWizard;
begin
  EnvPage := CreateInputQueryPage(
    wpSelectTasks,
    'Administrator password',
    'QUIZ_ADMIN_PASS environment variable',
    'Enter a password only if you selected the optional environment-variable task.'
  );
  EnvPage.Add('&Password:', True);
end;
