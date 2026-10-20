# patch work/out level files into the unpacked Remix, boot, go to Continue Story Mode, capture
param([string]$Tag = "run", [int]$Wait = 25, [switch]$NewStory)
$root = "C:\Users\tonyk\Documents\GitHub\THX"
$c = "$root\tools\ppsspp_ctl.ps1"; $s = "$root\work\shots"
$U = "$root\extracted\remix_psp\PSP_GAME\USRDIR"
$hed = "$root\tools\hed.py"
python $hed replace "$U\datap.hed" "$U\datap.wad" '\levels\tr\tr.psp_level' "$root\work\out\tr.psp_level"
python $hed replace "$U\datap.hed" "$U\datap.wad" '\levels\tr\tr.col.ps2' "$root\work\out\tr.col.ps2"
if (Test-Path "$root\work\out\tr_sky.psp_level") {
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\levels\tr_sky\tr_sky.psp_level' "$root\work\out\tr_sky.psp_level"
}
if (Test-Path "$root\work\out\tr.qb") {
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\levels\tr\tr.qb' "$root\work\out\tr.qb"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\pre\tr_scripts.pre' "$root\work\out\tr_scripts.pre"
}
if (Test-Path "$root\work\story\tr_scripts.pre") {
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\levels\tr\tr.qb' "$root\work\story\tr.qb"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\levels\tr\tr_scripts.qb' "$root\work\story\tr_scripts.qb"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\pre\tr_scripts.pre' "$root\work\story\tr_scripts.pre"
}
if (Test-Path "$root\work\hudout\panelsprites.pre") {
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\pre\panelsprites.pre' "$root\work\hudout\panelsprites.pre"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\pre\qb_scripts.pre' "$root\work\hudout\qb_scripts.pre"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\scripts\game\menu\themes.qb' "$root\work\hudout\loose\themes.qb"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\scripts\game\menu\panelstuff.qb' "$root\work\hudout\loose\panelstuff.qb"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\pre\themes.pre' "$root\work\hudout\themes.pre"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\images\themes\de_theme\de_sponsor.img.psp' "$root\work\hudout\loose\DE_sponsor.img.psp"
    foreach ($n in 'score_small','special','specialbar','balancemeter','balancearrow','balancearrow_glow') {
        python $hed replace "$U\datap.hed" "$U\datap.wad" "\images\panelsprites\$n.img.psp" "$root\work\hudout\loose\$n.img.psp"
    }
}
if (Test-Path "$root\work\story\qb_scripts.pre") {
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\pre\qb_scripts.pre' "$root\work\story\qb_scripts.pre"
    python $hed replace "$U\datap.hed" "$U\datap.wad" '\scripts\game\menu\chapter_info.qb' "$root\work\story\chapter_info.qb"
}
& $c start "$root\extracted\remix_psp" | Out-Null
Start-Sleep 25; & $c key z | Out-Null
foreach ($i in 1..3) { Start-Sleep 6; & $c key ENTER | Out-Null }
Start-Sleep 8; & $c key z | Out-Null
Start-Sleep 18; & $c key z | Out-Null
if ($NewStory) {
    # load screen -> wheel (Story Mode) -> Start New Story Mode -> Yes -> Normal
    Start-Sleep 16; & $c key z | Out-Null
    Start-Sleep 5; & $c key z | Out-Null
    Start-Sleep 4; & $c key DOWN | Out-Null; Start-Sleep 1; & $c key z | Out-Null
    Start-Sleep 3; & $c key DOWN | Out-Null; Start-Sleep 1; & $c key z | Out-Null
    Start-Sleep 4; & $c key z | Out-Null
    foreach ($i in 1..10) { Start-Sleep 4; & $c shot "$s\${Tag}_ns$i.png" | Out-Null }
    return
}
Start-Sleep 16; & $c key z | Out-Null
Start-Sleep 5; & $c key z | Out-Null
Start-Sleep 5; & $c key z | Out-Null
Start-Sleep $Wait; & $c shot "$s\${Tag}_1.png"
