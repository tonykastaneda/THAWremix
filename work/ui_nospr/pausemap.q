; THAW's pause menu map (gamemenu_pause: pause_menu_map) for Hollywood on Remix: THAW's own map
; image (ho_level_map) and its skater arrow (Bike_arrow), placed with THAW's numbers for Z_HO
; (map_scale 2.4, map_conversion 0.013 per inch). (-949.4375, -2423.4375) is THAW's map_offset plus the shift the
; level was built with (tools/thawui.py fills it in), so Remix world positions land where THAW's
; would. THAW's compass blips are left out (Remix has no CompassManager).

script hw_pause_map
wait 5 gameframes
SetScreenElementLock id = pause_menu off
SetScreenElementLock id = pause_vmenu off
CreateScreenElement {
Type = ContainerElement
parent = current_menu_anchor
id = map_piece_container
dims = (400, 400)
Pos = (180, 240)
just = [ center , center ]
internal_just = [ center center ]
scale = 2.4
alpha = 0
}
DoScreenElementMorph id = <> id alpha = 1 time = 0.3
map_pos = (200, 200)
CreateScreenElement {
Type = SpriteElement
parent = map_piece_container
id = level_map
Texture = ho_level_map
rgba = [ 128 128 128 128 ]
just = [ center , center ]
Pos = <> map_pos
z_priority = 5
}
skater : Obj_GetPosition
skater : GetHeading
arrow_pos = ( ( <> Pos . (1, 0, 0) ) * (1, 0) + ( <> Pos . (0, 0, 1) ) * (0, 1) )
arrow_pos = ( <> arrow_pos - (-949.4375, -2423.4375) )
arrow_pos = ( <> arrow_pos * 0.013 )
CreateScreenElement {
Type = SpriteElement
parent = map_piece_container
id = skater_arrow
Texture = Bike_arrow
rgba = [ 123 63 6 108 ]
just = [ center , top ]
Pos = ( <> map_pos + <> arrow_pos )
scale = ( 1.1 / 2.4 )
z_priority = 40
rot_angle = ( <> heading + 90 )
}
RunScriptOnScreenElement id = skater_arrow hw_pause_map_pulse
endscript

; THAW's pause_menu_map_pulse, its random first wait fixed at 0.2 s
script hw_pause_map_pulse time = 0.3
wait 0.2 seconds
while
DoMorph alpha = 0.0 time = <> time
wait <> time seconds
DoMorph alpha = 1.0 time = <> time
wait ( <> time + 0.1 ) seconds
repeat
endscript
