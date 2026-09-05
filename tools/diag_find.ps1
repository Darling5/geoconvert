$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WB {
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowW(string c, string t);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
'@
$TITLE = 'geoconvert — 三维模型转换器'
$proc = Start-Process -FilePath python -ArgumentList '-u','-m','geoconvert' -WorkingDirectory 'D:\WEB\zicaiduck\geo-convert' -WindowStyle Hidden -PassThru
try {
    $found = $null
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 400
        $script:TargetPid = $proc.Id
        $script:Hit = $null
        $cb = { param($h, $l)
            $sb = New-Object System.Text.StringBuilder 256
            [WB]::GetWindowTextW($h, $sb, 256) | Out-Null
            $procId = 0
            [WB]::GetWindowThreadProcessId($h, [ref]$procId) | Out-Null
            if ($procId -eq $script:TargetPid -and $sb.ToString().StartsWith('geoconvert')) { $script:Hit = $sb.ToString() }
            return $true }
        [WB]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
        if ($script:Hit) { $found = $script:Hit; break }
    }
    Write-Output ('ENUM title=[' + $found + ']')
    $codes = ($found.ToCharArray() | ForEach-Object { [int]$_ }) -join ','
    Write-Output ('ENUM codes=' + $codes)
    $tcodes = ($TITLE.ToCharArray() | ForEach-Object { [int]$_ }) -join ','
    Write-Output ('WANT codes=' + $tcodes)
    $h = [WB]::FindWindowW($null, $TITLE)
    Write-Output ('FindWindowW hwnd=' + $h)
} finally {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
