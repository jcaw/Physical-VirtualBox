@echo on

REM Run the rest in an elevated command prompt.
(
  set "params=%*"
  cd /d "%~dp0" && (
    if exist "%temp%\getadmin.vbs" del "%temp%\getadmin.vbs"
  ) && fsutil dirty query %systemdrive% 1>nul 2>nul || (
    echo Set UAC = CreateObject^("Shell.Application"^) : UAC.ShellExecute "cmd.exe", "/k cd ""%~sdp0"" && %~s0 %params%", "", "runas", 1 >> "%temp%\getadmin.vbs" && "%temp%\getadmin.vbs" && exit /B
  )
)

pip install -r ./requirements.txt --upgrade
pyinstaller ./launch_disk_in_virtualbox.py --uac-admin --onefile --noconfirm --console