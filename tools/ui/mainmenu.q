; Remix's main menu as THAW's: a column of tilted labels (THAW's create_base_main_menu, in
; z_mainmenu_scripts) instead of the spinning wheel. Remix's own setup and every item's handler stay
; (main_menu_exit with Remix's new_menu_script / change_gamemode, from its wheel list); THAW's order
; and wording, with Remix's Horse in THAW's 2-Player slot and WiFi Play in Online Play's.
; Replaces create_main_menu in levels\mainmenu\mainmenu_scripts.qb.

script create_main_menu
0x5426d0cd
change main_menu_return_to_createamodes = 0
SetPreferencesFromUI prefs = splitscreen field = "max_players" string = "num" Checksum = none num = 1
SetNetworkMode
UnpauseMusicAndStreams
UnPauseObjects
change in_options_menu = 0
SetNetworkMode
SetMemThreadSafe off
main_menu_wait_until_all_clear
spin_menu_skater_script Reset
KillSpawnedScript Name = TemporarilyDisableInput
spawnscript TemporarilyDisableInput params = { time = 400 }
SetMenuPadMappings [ active
use_as_first
]
; the Wheel of Loogies is 3D level geometry (wol_pie_*, wol_lightbulb_*): hidden
0x0a167145 On = 0
make_label_menu Pos = (40, 120) spacing = 6
add_label_menu_item {
text = 'STORY MODE'
rot = -3
padding = 30
pad_choose_script = main_menu_exit
pad_choose_params = { new_menu_script = create_gamemode_options_menu change_gamemode = change_gamemode_career 0xef366c9a no_spin_animation }
focus_params = { attract_timer }
}
add_label_menu_item {
text = 'CLASSIC MODE'
rot = 1
padding = 30
pad_choose_script = main_menu_exit
pad_choose_params = { new_menu_script = create_gamemode_options_menu change_gamemode = change_gamemode_classic 0xef366c9a no_spin_animation }
focus_params = { attract_timer }
}
add_label_menu_item {
text = 'CREATE-A-MODES'
rot = -2
padding = 30
label_offset = (5, 0)
pad_choose_script = main_menu_exit
pad_choose_params = { new_menu_script = create_createamodes_menu change_gamemode = change_gamemode_singlesession 0xef366c9a no_spin_animation }
focus_params = { attract_timer }
}
add_label_menu_item {
text = 'HORSE'
rot = -2
padding = 30
label_offset = (20, 0)
pad_choose_script = main_menu_exit
pad_choose_params = { new_menu_script = 0x00303383 change_gamemode = change_gamemode_freeskate_2p 0xef366c9a do_loading_logo no_spin_animation }
focus_params = { attract_timer }
}
add_label_menu_item {
text = 'HIGH SCORE / FREE SKATE'
rot = -3
padding = 40
label_offset = (10, 0)
pad_choose_script = main_menu_exit
pad_choose_params = { new_menu_script = launch_select_skater_menu change_gamemode = change_gamemode_singlesession 0xef366c9a do_loading_logo no_spin_animation }
focus_params = { attract_timer }
}
add_label_menu_item {
text = 'WIFI PLAY'
rot = 2
padding = 30
label_offset = (30, 0)
pad_choose_script = main_menu_exit
pad_choose_params = { new_menu_script = select_thug_online_play change_gamemode = change_gamemode_net 0xef366c9a do_loading_logo no_spin_animation }
focus_params = { attract_timer }
}
add_label_menu_item {
text = 'OPTIONS'
rot = -2
padding = 30
pad_choose_script = main_menu_exit
pad_choose_params = { new_menu_script = create_setup_options_menu 0xef366c9a no_spin_animation }
focus_params = { attract_timer }
}
SetScreenElementProps {
id = current_menu
event_handlers = [
{ pad_up reset_attract_mode_timer }
{ pad_down reset_attract_mode_timer }
]
}
create_helper_text generic_helper_text_no_back
FireEvent Type = focus target = current_menu
UnPauseSkaters
UnpauseMusicAndStreams
spin_menu_camera_init
KillSpawnedScript Name = attract_mode_timer
spawnscript attract_mode_timer
SpawnSecondControllerCheck
if ( layer_infos_need_resetting = 1 )
edit_graphic_reset_layer_infos
edit_graphic_apply_graphic_from_save
change layer_infos_need_resetting = 0
endif
wait 5 gameframe
kill_start_key_binding
endscript
