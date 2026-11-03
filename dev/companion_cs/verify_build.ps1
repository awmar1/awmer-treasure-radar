# Builds Companion.cs + Detect.cs in a temporary folder and compares the result with a shipped exe, byte for byte. This
# compiler has no /deterministic: every build differs in the PE timestamp, the module id (MVID) and one generated GUID
# name, and in nothing else. So the three places are allowed to differ, and everything else must match.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File dev\companion_cs\verify_build.ps1 C:\path\TreasureRadarCompanion.exe
param([Parameter(Mandatory = $true)][string]$Exe)
$ErrorActionPreference = 'Stop'
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('tr_verify_' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $tmp | Out-Null
try {
    $mine = Join-Path $tmp 'TreasureRadarCompanion.exe'
    & $csc /nologo /noconfig /nostdlib- /target:winexe /platform:x64 /optimize+ /debug- /warn:4 `
        /r:System.dll /r:System.Core.dll /r:System.Drawing.dll /r:System.Numerics.dll `
        "/out:$mine" "$PSScriptRoot\Companion.cs" "$PSScriptRoot\Detect.cs"
    if ($LASTEXITCODE -ne 0) { throw 'the build failed' }
    $a = [IO.File]::ReadAllBytes((Resolve-Path $Exe))
    $b = [IO.File]::ReadAllBytes($mine)
    if ($a.Length -ne $b.Length) { Write-Output "DIFFERENT: $($a.Length) bytes here, $($b.Length) from the source"; exit 1 }
    $stamp = [BitConverter]::ToInt32($a, 0x3C) + 8
    # runs of differing bytes, two runs joined when under 8 bytes apart (a GUID can match by chance in places)
    $runs = @()
    for ($i = 0; $i -lt $a.Length; $i++) {
        if ($a[$i] -eq $b[$i]) { continue }
        if ($runs.Count -and $i - $runs[-1][1] -lt 8) { $runs[-1][1] = $i } else { $runs += , @($i, $i) }
    }
    $bad = 0
    foreach ($r in $runs) {
        $n = $r[1] - $r[0] + 1
        $what = if ($r[0] -ge $stamp -and $r[1] -lt $stamp + 4) { 'PE timestamp' }
                elseif ($n -le 16) { 'the MVID (16 bytes)' }
                elseif ($n -le 36) { 'the generated GUID name (36 characters)' }
                else { $bad++; 'NOT EXPECTED' }
        Write-Output ('  0x{0:X}: {1} bytes, {2}' -f $r[0], $n, $what)
    }
    if ($bad -or $runs.Count -gt 3) { Write-Output 'DIFFERENT: this exe was not built from this source'; exit 1 }
    Write-Output 'MATCH: same code as this source, apart from the build-stamp bytes above'
} finally {
    Remove-Item -Recurse -Force $tmp
}
