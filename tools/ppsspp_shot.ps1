# Boot a PSP game folder or ISO in PPSSPP, press keys on a schedule, save window captures, exit.
#   ppsspp_shot.ps1 -Game <path> -Out <png prefix> [-Keys "20:ENTER,5:z,10:shot"] [-Exe <PPSSPPWindows64.exe>]
# Each -Keys item is "<seconds to wait>:<key>"; "shot" saves <prefix>_<n>.png instead of pressing a key.
# Keys use PPSSPP's default keyboard map (z = cross, x = circle, ENTER = start, arrows = d-pad).
param(
    [Parameter(Mandatory)] [string]$Game,
    [Parameter(Mandatory)] [string]$Out,
    [string]$Keys = "30:shot",
    [string]$Exe = "E:\SYSTEMS\PPSSPP\PPSSPPWindows64.exe"
)
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class PspWin {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
'@
[PspWin]::SetProcessDPIAware() | Out-Null
$vk = @{ ENTER = 0x0D; UP = 0x26; DOWN = 0x28; LEFT = 0x25; RIGHT = 0x27; SPACE = 0x20; ESC = 0x1B }
$p = Start-Process $Exe -ArgumentList "`"$Game`"", "--windowed" -PassThru
$n = 0
try {
    foreach ($item in $Keys.Split(',')) {
        $wait, $key = $item.Split(':')
        Start-Sleep -Seconds ([double]$wait)
        $p.Refresh()
        $h = $p.MainWindowHandle
        if ($key -eq 'shot') {
            $r = New-Object PspWin+RECT
            [PspWin]::GetWindowRect($h, [ref]$r) | Out-Null
            $bmp = New-Object Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
            $g = [Drawing.Graphics]::FromImage($bmp)
            $dc = $g.GetHdc()
            [PspWin]::PrintWindow($h, $dc, 2) | Out-Null
            $g.ReleaseHdc($dc)
            $n++
            $bmp.Save("${Out}_$n.png")
            "saved ${Out}_$n.png ($($bmp.Width)x$($bmp.Height))"
        } else {
            $code = if ($vk.ContainsKey($key)) { $vk[$key] } else { [byte][char]$key.ToUpper() }
            $scan = [byte][PspWin]::MapVirtualKey($code, 0)
            [PspWin]::SetForegroundWindow($h) | Out-Null
            Start-Sleep -Milliseconds 150
            [PspWin]::keybd_event($code, $scan, 0, [UIntPtr]::Zero)
            Start-Sleep -Milliseconds 120
            [PspWin]::keybd_event($code, $scan, 2, [UIntPtr]::Zero)
        }
    }
} finally {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}
