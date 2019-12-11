REM Run an elevated prompt. Include this snippet in another bat file to run the
REM rest of the file in an elevated prompt.


set "params=%*"
cd /d "%~dp0" && (
   if exist "%temp%\getadmin.vbs" del "%temp%\getadmin.vbs"
) && fsutil dirty query %systemdrive% 1>nul 2>nul || (
   echo Set UAC = CreateObject^("Shell.Application"^) : UAC.ShellExecute "cmd.exe", "/k cd ""%~sdp0"" && %~s0 %params%", "", "runas", 1 >> "%temp%\getadmin.vbs" && "%temp%\getadmin.vbs" && exit /B
)