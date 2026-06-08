
; =============== QuizApp.iss ===============
; Inno Setup Script for QuizApp (Windows)
; Работи с PyInstaller билд: --onefile ИЛИ --onedir
; Автор: ППМГ проект (Светослав Иванов)
; ------------------------------------------

#define AppName        "QuizApp"
#define AppVersion     "1.0.3"
#define AppPublisher   "PPMG Ekarh Antim I"
#define AppURL         "https://pmg-vd.org"
#define ExeName        "QuizApp.exe"

; Път до твоя PyInstaller dist (съотнеси към .iss файла или ползвай абсолютен път)
#define DistDir        "dist"

[Setup]
AppId={{C1C0C7C2-17A9-4D9D-8ADE-QUIZ-APP-EXAMPLE-ID}}
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

; 64-bit инсталация в Program Files (x64), ако ОС е x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

; Икона на инсталатора (по желание):
; SetupIconFile=images\logo.ico

Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#ExeName}
OutputDir=output
OutputBaseFilename=Setup_{#AppName}_{#AppVersion}

; Ако задаваме системна променлива на средата (ENV),
; това ще прати уведомление към системата след инсталация/деинсталация:
ChangesEnvironment=yes

[Languages]
Name: "bulgarian"; MessagesFile: "compiler:Languages\Bulgarian.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Създай икона на работния плот"; GroupDescription: "Икони:"; Flags: unchecked
Name: "setenv"; Description: "Задай системна променлива QUIZ_ADMIN_PASS (админ парола) по време на инсталацията"; GroupDescription: "Допълнителни настройки:"; Flags: unchecked

[Dirs]
; Създай папки за данни в {app} и дай права за запис на обикновени потребители (ученици).
Name: "{app}\reports"; Permissions: users-modify; Flags: uninsalwaysuninstall
Name: "{app}\questions"; Permissions: users-modify; Flags: uninsalwaysuninstall
; Ако искаш и images/sounds/fonts да са записваеми (примерно за смяна на ресурси), разкоментирай:
; Name: "{app}\images";   Permissions: users-modify
; Name: "{app}\sounds";   Permissions: users-modify
; Name: "{app}\fonts";    Permissions: users-modify

[Files]
; ---------------------- ONEFILE (PyInstaller --onefile) ----------------------
; Активирай следния ред, ако използваш --onefile билд:
Source: "{#DistDir}\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Ако имаш начални въпроси за импорт (seed pool), можеш да ги копираш в {app}\questions:
; Source: "questions\*"; DestDir: "{app}\questions"; Flags: recursesubdirs createallsubdirs ignoreversion

; ---------------------- ONEDIR (PyInstaller --onedir) -----------------------
; АКО използваш --onedir билд, коментирай горното ONEFILE и активирай този блок:
; Source: "{#DistDir}\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

; ONEFILE (остават и другите Source редове)
Source: "grading_scale.csv"; DestDir: "{app}"; Flags: ignoreversion
Source: "instructions.docx"; DestDir: "{app}"; Flags: ignoreversion

; ONEDIR (ако ползваш целия dist/QuizApp, добави също този ред извън onedir блока)
; Source: "grading_scale.csv"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"; WorkingDir: "{app}"
Name: "{group}\Деинсталирай {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; WorkingDir: "{app}"; Tasks: desktopicon


[Files]
; onefile: копираме .exe
Source: "{#DistDir}\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion

; добавяме ресурсни директории (seed) от проекта:
Source: "images\*";   DestDir: "{app}\images";   Flags: recursesubdirs createallsubdirs ignoreversion
Source: "sounds\*";   DestDir: "{app}\sounds";   Flags: recursesubdirs createallsubdirs ignoreversion
Source: "fonts\*";    DestDir: "{app}\fonts";    Flags: recursesubdirs createallsubdirs ignoreversion
; по желание начален пул въпроси:
Source: "questions\*"; DestDir: "{app}\questions"; Flags: recursesubdirs createallsubdirs ignoreversion


[Run]
; Предложи стартиране на приложението след инсталиране
Filename: "{app}\{#ExeName}"; Description: "Стартирай {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifdoesntexist

[Registry]
; По желание: задаване на системна ENV променлива QUIZ_ADMIN_PASS от инсталатора (ако е избрано Tasks:setenv)
; Използваме стойността, върната от функцията {code:GetAdminPass}
; ВНИМАНИЕ: това влиза в системния регистър (HKLM) - препоръчва се за училищни машини.
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
    ValueType: expandsz; ValueName: "QUIZ_ADMIN_PASS"; ValueData: "{code:GetAdminPass}"; Flags: uninsdeletevalue; Tasks: setenv

[Code]
var
  EnvPage: TInputQueryWizardPage;

function IsTaskSelected(const TaskName: String): Boolean;
begin
  Result := WizardIsTaskSelected(TaskName);
end;

function GetAdminPass(Value: string): string;
begin
  Result := '';
  if IsTaskSelected('setenv') then
  begin
    if Assigned(EnvPage) and (EnvPage.Values[0] <> '') then
    begin
      Result := EnvPage.Values[0];
    end;
  end;
end;

procedure InitializeWizard;
begin
  { Създаваме страница за въвеждане на админ парола, ПАКО И САМО ако е избран task "setenv" }
  EnvPage := CreateInputQueryPage(
    wpSelectTasks,
    'Администраторска парола (по избор)',
    'Системна променлива QUIZ_ADMIN_PASS',
    'Ако желаете инсталаторът да зададе системна променлива QUIZ_ADMIN_PASS (достъпна за всички потребители), ' +
    'въведете стойността тук. Оставете празно, ако не желаете.'
  );
  EnvPage.Add('&Парола (ще бъде съхранена в системния регистър):', False);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  { Ако е избран task "setenv" и сме на страницата EnvPage – позволи празна стойност, но предупреди }
  if (CurPageID = EnvPage.ID) and IsTaskSelected('setenv') then
  begin
    { Няма задължителен контрол, но може да добавиш проверки тук }
    Result := True;
  end;
end;
