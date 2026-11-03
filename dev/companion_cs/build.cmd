@echo off
rem Builds dev\build\companion\TreasureRadarCompanion.exe with the C# compiler every Windows 10/11 has. No SDK, no NuGet.
setlocal
set CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe
set HERE=%~dp0
set OUT=%HERE%..\build\companion
if not exist "%OUT%" mkdir "%OUT%"
"%CSC%" /nologo /noconfig /nostdlib- /target:winexe /platform:x64 /optimize+ /debug- /warn:4 ^
  /r:System.dll /r:System.Core.dll /r:System.Drawing.dll /r:System.Numerics.dll ^
  /out:"%OUT%\TreasureRadarCompanion.exe" "%HERE%Companion.cs" "%HERE%Detect.cs"
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "$f=Get-Item '%OUT%\TreasureRadarCompanion.exe'; '{0}  {1} bytes  sha256 {2}' -f $f.Name,$f.Length,(Get-FileHash $f.FullName -Algorithm SHA256).Hash"
