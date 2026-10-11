# Drive a running PPSSPP step by step (ppsspp_shot.ps1 runs a fixed schedule instead).
#   ppsspp_ctl.ps1 start <game path>       launch windowed
#   ppsspp_ctl.ps1 key <key> [hold ms]     press a key (z = cross, x = circle, ENTER = start, arrows)
#   ppsspp_ctl.ps1 shot <png>              save a window capture
#   ppsspp_ctl.ps1 stop
param(
    [Parameter(Mandatory)] [string]$Action,
    [string]$Arg = "",
    [int]$Hold = 120,
    [string]$Exe = "E:\SYSTEMS\PPSSPP\PPSSPPWindows64.exe"
)
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class PspCtl {
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
'@
[PspCtl]::SetProcessDPIAware() | Out-Null
$vk = @{ ENTER = 0x0D; UP = 0x26; DOWN = 0x28; LEFT = 0x25; RIGHT = 0x27; SPACE = 0x20; ESC = 0x1B }
$name = [IO.Path]::GetFileNameWithoutExtension($Exe)
$p = Get-Process -Name $name -ErrorAction SilentlyContinue | Select-Object -First 1
switch ($Action) {
    'start' {
        if ($p) { Stop-Process -Id $p.Id -Force; Start-Sleep 1 }
        Start-Process $Exe -ArgumentList "`"$Arg`"", "--windowed" | Out-Null
        "started"
    }
    'stop' { if ($p) { Stop-Process -Id $p.Id -Force }; "stopped" }
    'key' {
        if (-not $p) { throw "PPSSPP not running" }
        # "q+w" presses keys together
        $codes = foreach ($k in $Arg.Split('+')) { if ($vk.ContainsKey($k)) { $vk[$k] } else { [byte][char]$k.ToUpper() } }
        [PspCtl]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
        Start-Sleep -Milliseconds 150
        foreach ($code in $codes) { [PspCtl]::keybd_event($code, [byte][PspCtl]::MapVirtualKey($code, 0), 0, [UIntPtr]::Zero) }
        Start-Sleep -Milliseconds $Hold
        foreach ($code in $codes) { [PspCtl]::keybd_event($code, [byte][PspCtl]::MapVirtualKey($code, 0), 2, [UIntPtr]::Zero) }
        "pressed $Arg"
    }
    'shot' {
        if (-not $p) { throw "PPSSPP not running" }
        $h = $p.MainWindowHandle
        $r = New-Object PspCtl+RECT
        [PspCtl]::GetWindowRect($h, [ref]$r) | Out-Null
        $bmp = New-Object Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
        $g = [Drawing.Graphics]::FromImage($bmp)
        $dc = $g.GetHdc()
        [PspCtl]::PrintWindow($h, $dc, 2) | Out-Null
        $g.ReleaseHdc($dc)
        $bmp.Save($Arg)
        "saved $Arg"
    }
}
