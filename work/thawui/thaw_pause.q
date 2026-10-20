script create_pause_menu
if ObjectExists id = skater
if not IsObserving
if skater : IsSkaterOnBike
SetAnalogStickActiveForMenus 1
endif
endif
endif
if ( in_telescope_cam = 1 )
pause_telescope_cam
else
if not IsObserving
AndrewRTripy_exit
endif
endif
if GotParam no_exit
set_pause_menu_allow_continue off
else
if root_window : GetSingleTag no_exit_pause_menu
no_exit = no_exit
endif
endif
if CustomParkMode editing
SetParkEditorPauseMode pause
endif
if not GotParam no_sound
endif
unhide_root_window
if ( inside_pause = 1 )
endif
if not GotParam no_actual_menu
if ( inside_pause = 0 )
hide_all_hud_items
hide_current_goal
endif
endif
if InNetGame
if not IsObserving
if ObjectExists id = skater
skater : NetDisablePlayerInput
endif
endif
else
if not GotParam no_actual_menu
if CustomParkMode editing
parked_setup_main_menu
PauseMusicAndStreams 1
build_pause_menu_parts
return
endif
if CustomParkMode testing
parked_setup_test_play_menu
PauseMusicAndStreams 1
build_pause_menu_parts
return
endif
if InSplitScreenGame
if not GameModeEquals is_coop
create_mp_pause_menu
PauseMusicAndStreams 1
build_pause_menu_parts
return
endif
endif
endif
endif
if ( inside_pause = 0 )
if MusicIsPaused
change music_was_paused = 1
else
change music_was_paused = 0
endif
endif
PauseMusicAndStreams 1
pause_rain
if GotParam no_actual_menu
return
endif
if ( in_cat_preview_mode = 1 )
create_CAT_pause_menu
return
endif
<> show_legend = 0
if GameModeEquals Is_Career
GetLevelStructureName
if not StructureContains structure = <> level_structure_name level_map
<> show_legend = 0
else
<> show_legend = 1
endif
endif
if not GotParam no_exit
if ( <> show_legend = 1 )
helper = {
helper_text_elements = [
{ text = "\\b6 = Map Legend" }
{ text = "\\b7/\\b4 = Select" }
{ text = "\\m1 = Back" }
{ text = "\\m0 = Accept" }
]
}
else
helper = generic_helper_text
endif
else
if ( <> show_legend = 1 )
helper = {
helper_text_elements = [
{ text = "\\b6 = Map Legend" }
{ text = "\\b7/\\b4 = Select" }
{ text = "\\m0 = Accept" }
]
}
else
helper = generic_helper_text_no_back
endif
endif
if InNetGame
menu_pos = (410, 35)
else
if GameModeEquals is_freeskate Is_SingleSession
menu_pos = (410, 120)
else
menu_pos = (410, 75)
endif
endif
if GotParam no_exit
make_label_menu {
Pos = <> menu_pos
pad_back_script = NullScript
menu_id = pause_menu
vmenu_id = pause_vmenu
spacing = 0
}
else
make_label_menu {
Pos = <> menu_pos
pad_back_script = handle_start_pressed
menu_id = pause_menu
vmenu_id = pause_vmenu
spacing = 0
}
endif
if GotParam no_exit
<> start_handler = NullScript
else
<> start_handler = handle_start_pressed
endif
if ( <> show_legend = 1 )
SetScreenElementProps {
id = pause_vmenu
event_handlers = [
{ pad_left pause_menu_legend }
{ pad_start <> start_handler }
]
}
else
SetScreenElementProps {
id = pause_vmenu
event_handlers = [
{ pad_start <> start_handler }
]
}
endif
kill_start_key_binding
add_music_track_text Pos = (575, 320)
white_poly_bg_effect
if InNetGame
if not IsXenon
paused_title_text
endif
else
paused_title_text
endif
if InNetGame
clock_pos = (-50, 0)
else
clock_pos = (-50, 58)
endif
CreateScreenElement {
Type = ContainerElement
parent = current_menu_anchor
id = clock_anchor
just = [ left center ]
Pos = <> clock_pos
}
if GameModeEquals Is_Career
pause_add_time_and_cash
GetLevelStructureName
if StructureContains structure = <> level_structure_name level_map
current_menu_anchor : Obj_SpawnScriptNow pause_menu_map
endif
endif
SetScreenElementLock id = clock_anchor off
if not IsObserving
pause_add_combo_records
endif
if GameModeEquals Is_SingleSession
if GoalManager_GoalIsActive Name = trickattack
add_label_menu_item {
text = "RETRY HIGH SCORE RUN"
rot = -6
scale = 0.85
label_offset = (-80, 0)
id = menu_retry_high_score_run
pad_choose_script = menu_select
pad_choose_params = { stop_streams menu_select_script = RetryCurrentGoal }
}
add_label_menu_item {
text = "END HIGH SCORE RUN"
rot = 0
scale = 0.85
label_offset = (-80, 0)
id = menu_end_high_score_run
pad_choose_script = menu_select
pad_choose_params = { menu_select_script = end_high_score_run }
}
else
add_label_menu_item {
text = "START HIGH SCORE RUN"
rot = -6
scale = 0.85
label_offset = (-80, 0)
id = menu_start_high_score_run
pad_choose_script = menu_select
pad_choose_params = { menu_select_script = TrickAttack_MenuStartRun }
}
endif
else
if not GotParam no_exit
add_label_menu_item {
text = "CONTINUE"
rot = 0
scale = 0.85
label_offset = (-20, 0)
id = menu_continue pad_choose_script = handle_pause_continue pad_choose_sound = generic_pause_exit_sound
}
endif
endif
if GameModeEquals is_goal_attack
if not IsObserving
GetGoalsMode
if ( <> goals = goals_created )
if GoalManager_CanRetryGoal
if GoalManager_GetLastGoalId
if not GoalManager_HasWonGoal Name = <> goal_id
add_label_menu_item {
text = "RETRY LAST GOAL"
rot = -2
scale = 0.85
label_offset = (-20, 0)
id = menu_retry_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration menu_select_script = RetryCurrentGoal }
}
endif
endif
endif
endif
endif
add_label_menu_item {
text = "VIEW GOALS"
rot = 4
scale = 0.85
label_offset = (-10, 0)
id = menu_view_goals pad_choose_script = create_view_selected_goals_menu pad_choose_params = { from_pause }
}
endif
if GameModeEquals Is_Career
if GoalManager_CanRetryGoal
add_label_menu_item {
text = "RETRY THIS MISSION"
rot = -2
scale = 0.85
label_offset = (-40, 0)
id = menu_retry_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration stop_streams menu_select_script = RetryCurrentGoal }
}
else
<> check_can_retry_last = 1
if GoalManager_GoalExists Name = ( goal_utility_last_goal_activated )
if GoalManager_GoalIsActive Name = ( goal_utility_last_goal_activated )
<> check_can_retry_last = 0
endif
endif
if ( ( in_telescope_cam ) = 1 )
<> check_can_retry_last = 0
endif
if ( <> check_can_retry_last = 1 )
if skater : IsSkaterOnBike
<> is_on_bike = 1
else
<> is_on_bike = 0
endif
if GoalManager_CanRetryLastGoal is_on_bike = <> is_on_bike
add_label_menu_item {
text = "RETRY LAST MISSION"
rot = -2
scale = 0.85
label_offset = (-40, 0)
id = menu_retry_last_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration stop_streams menu_select_script = GoalManager_RestartLastGoal }
}
endif
endif
endif
if not game_progress_disallow_save
if GoalManager_GoalIsActive Name = ( goal_utility_last_goal_activated )
add_label_menu_item {
text = "QUIT MISSION"
rot = 0
scale = 0.85
label_offset = (-20, 0)
id = menu_quit_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration stop_streams menu_select_script = goal_quit_current_goal }
}
endif
endif
if NodeArrayBusy
add_label_menu_item {
text = "VIEW MISSIONS"
rot = -5
scale = 0.85
label_offset = (-20, 0)
id = menu_chapters pad_choose_script = view_goals_menu_create
not_focusable
}
else
add_label_menu_item {
text = "VIEW MISSIONS"
rot = -5
scale = 0.85
label_offset = (-20, 0)
id = menu_chapters pad_choose_script = view_goals_menu_create
}
endif
add_label_menu_item {
text = "TEXT MESSAGES"
rot = -2
scale = 0.85
label_offset = (-30, 0)
id = menu_pager pad_choose_script = pager_window_create
}
endif
if GameModeEquals is_classic
classic_mode_menu_add_pause_options
endif
display_level_select = 1
if InNetGame
display_level_select = 0
endif
if GameModeEquals Is_Career
if not IsTrue all_levels_unlocked
display_level_select = 0
endif
endif
if GameModeEquals is_classic
if not GotParam no_exit
display_level_select = 0
endif
endif
if GetGlobalFlag flag = CHEAT_DEBUG_MENU_UNLOCKED
if not InNetGame
display_level_select = 1
endif
endif
if ( <> display_level_select = 1 )
add_label_menu_item {
text = "CHANGE AREA"
rot = -2
scale = 0.85
label_offset = (-10, 0)
id = menu_level_select
pad_choose_script = launch_level_select_menu
}
endif
if InNetGame
if IsHost
if GameModeEquals is_lobby
if not NetworkGamePending
if not ChangeLevelPending
add_label_menu_item {
text = "START GAME"
rot = -4
scale = 0.85
label_offset = (-10, 0)
id = menu_network_start_select pad_choose_script = network_game_options_selected
}
endif
endif
else
add_label_menu_item {
text = "END CURRENT GAME"
rot = -2
scale = 0.85
label_offset = (-20, 0)
id = menu_network_end_select pad_choose_script = network_end_game_selected
}
endif
endif
endif
if InNetGame
if not NetworkGamePending
if OnServer
if ( ( IsXbox ) or ( IsXenon ) )
add_label_menu_item {
text = "HOST OPTIONS"
rot = -2
scale = 0.85
label_offset = (-20, 0)
id = menu_network_server_opts_select pad_choose_script = network_options_selected
}
else
add_label_menu_item {
text = "SERVER OPTIONS"
rot = -2
scale = 0.85
label_offset = (-30, 0)
id = menu_network_server_opts_select pad_choose_script = network_options_selected
}
endif
endif
if IsHost
if GameModeEquals is_lobby
if not OnServer
if OnXbox
add_roundbar_menu_item text = "HOST OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected
add_label_menu_item {
text = "HOST OPTIONS"
rot = -2
scale = 0.85
label_offset = (-20, 0)
id = menu_network_server_opts_select pad_choose_script = network_options_selected
}
else
add_label_menu_item {
text = "SERVER OPTIONS"
rot = -2
scale = 0.85
label_offset = (-20, 0)
id = menu_network_server_opts_select pad_choose_script = network_options_selected
}
endif
endif
endif
endif
endif
endif
if InNetGame
if not IsObserving
<> game_active = 0
if GoalManager_HasActiveGoals count_all
<> game_active = 1
endif
if ( <> game_active = 1 )
<> trick_text = "VIEW TRICKS"
<> trick_helper = view_tricks_helper_desc
else
if not GoalManager_HasActiveGoals
<> trick_text = "EDIT TRICKS"
<> trick_helper = edit_tricks_helper_desc
else
<> trick_text = "VIEW TRICKS"
<> trick_helper = view_tricks_helper_desc
endif
endif
add_label_menu_item {
text = <> trick_text
rot = -4
scale = 0.85
label_offset = (-10, 0)
id = menu_cas pad_choose_script = create_edit_tricks_menu
}
endif
endif
if InNetGame
if IsHost
if GameModeEquals is_lobby
if not NetworkGamePending
if not ChangeLevelPending
add_label_menu_item {
text = "CHANGE AREA"
rot = -4
scale = 0.85
label_offset = (-10, 0)
id = menu_level_select pad_choose_script = launch_level_select_menu pad_choose_params = { show_warning }
}
endif
endif
endif
endif
if ( ( IsPs2 ) or ( IsPC ) )
if IsTrue Bootstrap_Build
add_label_menu_item {
text = "CHANGE AREA"
rot = -4
scale = 0.85
label_offset = (-10, 0)
id = menu_network_remove_select pad_choose_script = launch_remove_players_menu not_focusable = not_focusable
}
else
add_label_menu_item {
text = "PLAYER LIST"
rot = -4
scale = 0.85
label_offset = (-10, 0)
id = menu_network_player_list_select pad_choose_script = launch_player_list_menu
}
if NetSessionFunc obj = presence func = profile_logged_in
add_label_menu_item {
text = "HOMIE LIST"
rot = -4
scale = 0.85
label_offset = (-10, 0)
id = menu_network_homie_list_select pad_choose_script = launch_homie_list
}
NetSessionFunc obj = presence func = get_num_notifications
if ( <> num_notifications > 0 )
add_label_menu_item {
text = "VIEW MESSAGES"
rot = -2
scale = 0.85
label_offset = (-20, 0)
id = menu_pager pad_choose_script = pager_window_create
}
endif
endif
endif
endif
endif
show_live_options = 0
if IsXbox
if NetSessionFunc func = presence_started
<> show_live_options = 1
endif
endif
if IsTrue in_telescope_cam
<> show_live_options = 0
endif
if ( <> show_live_options = 1 )
add_label_menu_item {
text = "XBOX LIVE OPTIONS"
rot = -2
scale = 0.85
label_offset = (-10, 0)
id = menu_network_live_options_select pad_choose_script = xboxlive_menu_options_push pad_choose_params = { from_pause_menu }
}
xboxlive_menu_notify_clone_sprite {
id = xbox_notification
parent = menu_network_live_options_select
clone_pos = (-4, 5)
z_priority = 5
}
endif
if not InNetGame
save_shown = 1
save_focusable = { }
if IsXenon
if not CheckForSignIn local
save_focusable = { not_focusable }
endif
endif
if GameModeEquals Is_Career
if game_progress_disallow_save
save_focusable = { not_focusable }
endif
endif
if GameModeEquals is_classic is_coop
if not root_window : GetSingleTag no_exit_pause_menu
save_shown = 0
endif
endif
if LevelIs Load_Sk5Ed
save_shown = 0
endif
if ( <> save_shown = 1 )
add_label_menu_item {
text = "SAVE GAME"
rot = -1
length = 150
scale = 0.85
id = menu_save_game
pad_choose_script = launch_pause_menu_save_game_sequence
<> save_focusable
}
endif
add_label_menu_item {
text = "YOUR PROGRESS"
rot = -2
scale = 0.85
label_offset = (-24, 0)
id = menu_your_options pad_choose_script = create_your_options_menu
}
endif
add_label_menu_item {
text = "GAME OPTIONS"
rot = -3
scale = 0.85
label_offset = (-33, 0)
id = menu_game_options pad_choose_script = create_options_menu
}
<> show_debug_menu = 0
if not CD
<> show_debug_menu = 1
else
if GetGlobalFlag flag = CHEAT_DEBUG_MENU_UNLOCKED
<> show_debug_menu = 1
endif
endif
if not IsPC
if ( <> show_debug_menu = 1 )
add_label_menu_item {
text = "DEBUG OPTIONS"
rot = -4
scale = 0.85
label_offset = (-17, 0)
id = debug_menu pad_choose_script = create_debug_options_menu
}
endif
endif
if not CD
if ( main_menu_jump_to_cas = 1 )
add_label_menu_item {
text = "BACK TO CAS"
rot = -4
scale = 0.85
label_offset = (-10, 0)
id = debug_cas_menu pad_choose_script = create_pre_cas_menu pad_choose_params = { load_assets = 1 }
}
endif
endif
if InNetGame
if not ( ( IsXbox ) or ( IsXenon ) )
add_label_menu_item {
text = "CHAT MESSAGE"
rot = -2
scale = 0.85
label_offset = (-10, 0)
id = menu_chat pad_choose_script = launch_chat_keyboard
}
endif
if not OnServer
if not IsObserving
if InInternetMode
if GameModeEquals is_lobby
if not NetSessionFunc obj = match func = IsRanked
if IsTrue Bootstrap_Build
if not GoalManager_HasActiveGoals
add_label_menu_item {
text = "OBSERVE"
rot = -4
scale = 0.85
label_offset = (-20, 0)
id = menu_network_observe_select pad_choose_script = chose_observe not_focusable = not_focusable
}
endif
else
if not GoalManager_HasActiveGoals
add_label_menu_item {
text = "OBSERVE"
rot = -4
scale = 0.85
label_offset = (-20, 0)
id = menu_network_observe_select pad_choose_script = chose_observe
}
endif
endif
endif
endif
endif
endif
endif
if IsXenon
add_label_menu_item {
text = "CURRENT PLAYERS"
rot = -2
scale = 0.85
label_offset = (-10, 0)
id = menu_network_live_options_select pad_choose_script = xbox360live_menu_options_push pad_choose_params = { from_pause_menu }
}
endif
add_label_menu_item {
text = "QUIT"
rot = 2
scale = 0.85
label_offset = (-10, 0)
id = menu_quit pad_choose_script = generic_menu_pad_choose pad_choose_params = { callback = launch_quit_game_dialog }
}
else
if CustomParkMode testing
printf "PARK EDITOR TEST PLAY MENU"
add_label_menu_item {
text = "VIEW MESSAGES"
rot = -2
scale = 0.85
label_offset = (-10, 0)
id = menu_skateshop pad_choose_script = menu_confirm_quit pad_choose_params = { yes_script = exit_test_play }
}
else
if GameModeEquals is_classic
classic_mode_menu_add_quit_option
else
if GameModeEquals Is_Career
if ( ( in_telescope_cam ) = 0 )
add_label_menu_item {
text = "QUIT"
rot = -5
scale = 0.85
label_offset = (30, 0)
id = menu_skateshop
pad_choose_script = generic_menu_pad_choose
pad_choose_params = { callback = career_mode_quit_dialog }
}
endif
else
add_label_menu_item {
text = "QUIT"
rot = -5
scale = 0.85
label_offset = (30, 0)
id = menu_skateshop
pad_choose_script = generic_menu_pad_choose
pad_choose_params = { callback = menu_confirm_quit }
}
endif
endif
endif
endif
kill_blur Start = 0
if root_window : GetSingleTag highlight_change_level
focus_data = { grid_index = 1 }
root_window : RemoveTags tags = [ highlight_change_level ]
endif
label_menu_finish show_deck = show_deck data = <> focus_data helper_text = <> helper
endscript

script confirm_end_mp_game
create_snazzy_dialog_box {
title = "END GAME?"
text = "If you end the current game, you will not be able to continue it.\\n\\nAre you sure?"
text_dims = (400, 0)
pad_back_script = create_mp_pause_menu
pad_back_params = no_animate
no_bg
buttons = [
{ text = "Yes" pad_choose_script = network_end_game_selected }
{ text = "No" pad_choose_script = create_mp_pause_menu pad_choose_params = no_animate }
]
}
endscript

script create_mp_pause_menu
dialog_box_exit
SetButtonEventMappings unblock_menu_input
make_label_menu {
menu_id = pause_menu
vmenu_id = pause_vmenu
pad_back_script = handle_start_pressed
title = "PAUSED"
title_pos = (30, 40)
Pos = (130, 130)
additional_create_script = pause_create_tipbox
additional_focus_script = pause_focus_tipbox
additional_unfocus_script = pause_unfocus_tipbox
helper_text = <> helper
}
create_helper_text generic_helper_text
add_label_menu_item {
text = "CONTINUE"
rot = 1
scale = 0.85
label_offset = (-20, 0)
id = menu_continue pad_choose_script = handle_start_pressed
}
add_label_menu_item {
text = "END CURRENT GAME"
rot = -2
scale = 0.85
label_offset = (-20, 0)
id = menu_network_end_select pad_choose_script = confirm_end_mp_game
}
add_label_menu_item {
text = "OPTIONS"
rot = 4
scale = 0.85
label_offset = (-10, 0)
id = menu_mp_options pad_choose_script = generic_menu_pad_choose pad_choose_params = { callback = create_options_menu }
}
label_menu_finish
endscript

script do_localized_pause_title
Pos = (500, 40)
if IsPal
if not English
CreateScreenElement {
Type = TextElement
parent = current_menu_anchor
id = localized_pause_title
font = small
text = "PAUSED"
Pos = <> Pos
just = [ right bottom ]
scale = 2
rgba = [ 128 40 10 128 ]
shadow
shadow_rgba = [ 0 , 0 , 0 , 128 ]
shadow_offs = (3, 3)
z_priority = 50
}
endif
endif
endscript

script exit_pause_menu
menu_id = current_menu_anchor
change check_for_unplugged_controllers = 0
KillSpawnedScript Name = pause_menu_map_pulse
if ScreenElementExists id = current_menu_anchor
FireEvent Type = unfocus target = current_menu_anchor
endif
ClearViewerObject
Debounce x time = 0.3
Debounce Triangle time = 0.3
Debounce circle time = 0.3
Debounce square time = 0.3
pause_menu_gradient off
change inside_pause = 0
change no_focus_sound = 1
unhide_current_goal
if not CD
change viewer_buttons_enabled = 1
endif
if not GetGlobalFlag flag = CAREER_ONETIMEINTRO
if ( in_telescope_cam = 0 )
show_all_hud_items
endif
endif
if InNetGame
if not IsObserving
if ObjectExists id = skater
skater : NetEnablePlayerInput
endif
endif
endif
if ObjectExists id = skater
if not IsObserving
if skater : IsSkaterOnBike
SetAnalogStickActiveForMenus 0
endif
endif
endif
unpausegame
possibly_add_temp_special_trick
PauseStream 0
if not GotParam dont_unpause_music
if ( music_was_paused = 0 )
PauseMusic 0
endif
endif
if root_window : GetSingleTag need_music_zone_refresh
root_window : RemoveTags tags = [ need_music_zone_refresh ]
SpawnScriptLater SFX_refresh_music_box_triggers params = { wait }
endif
unpause_rain
GoalManager_UnpauseAllGoals
if ObjectExists id = <> menu_id
DestroyScreenElement id = <> menu_id
endif
SetScreenElementProps id = root_window tags = { menu_state = off }
if not GotParam dont_restore_start_key_binding
restore_start_key_binding
KillSpawnedScript Name = TemporarilyDisableInput
SpawnScriptLater TemporarilyDisableInput params = { time = 500 }
endif
if not InNetGame
if not GameModeEquals is_horse
UnPauseSkaters
endif
endif
if ( in_telescope_cam = 1 )
restore_telescope_camera
endif
if IsXbox
xboxlive_voice_attachment_finished
xboxlive_menu_friends_close
endif
if not InFrontEnd
menu_stack_clear
endif
change check_for_unplugged_controllers = 1
endscript

script pause_launch_level
skater : StatsManager_Reset
if ( <> level = load_cas )
temp = <> level
GetCurrentLevel
array = return_to_level
SetArrayElement arrayname = array index = 0 newvalue = <> level
level = <> temp
endif
if GameModeEquals { Is_Career }
GoalManager_DeactivateAllGoals { force_all }
endif
change_level <...>
endscript

script white_poly_bg_effect
pause_menu_gradient off
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = white_bg
Texture = white2
rgba = [ 128 128 128 30 ]
just = [ center , center ]
Pos = (320, 224)
scale = (80, 80)
z_priority = -10
rot_angle = 0
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_white_bar
Texture = white2
rgba = [ 128 128 128 58 ]
just = [ center , center ]
Pos = (315, 66)
scale = (80, 6)
z_priority = -1
rot_angle = 11
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_purple_bar
Texture = goal_grad
rgba = [ 62 1 108 45 ]
just = [ center , center ]
Pos = (120, 150)
scale = (6, 100)
z_priority = -10
rot_angle = 100
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_purple_bar2
Texture = goal_grad
rgba = [ 62 1 108 45 ]
just = [ center , center ]
Pos = (514, 220)
scale = (6, 100)
z_priority = -10
rot_angle = 100
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_purple_bar3
Texture = goal_grad
rgba = [ 62 1 108 50 ]
just = [ center , left ]
Pos = (30, -12)
scale = (0.3, 190)
z_priority = 0
rot_angle = -80
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_purple_bar4
Texture = goal_grad
rgba = [ 0 0 0 128 ]
just = [ center , left ]
Pos = (0, 30)
scale = (0.4, 190)
z_priority = -10
rot_angle = -80
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_black_bar1
Texture = goal_grad
rgba = [ 0 0 0 20 ]
just = [ center , top ]
Pos = (580, 125)
scale = (1, 150)
z_priority = 0
rot_angle = 99.5
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_black_bar2
Texture = goal_grad
rgba = [ 0 0 0 50 ]
just = [ center , top ]
Pos = (650, 53)
scale = (3.5, 160)
z_priority = 1
rot_angle = 100
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = paused_black_bar3
Texture = white2
rgba = [ 0 0 0 120 ]
just = [ center , top ]
Pos = (550, 80)
scale = (0.5, 150)
z_priority = -10
rot_angle = 99
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = extra_star_1
Texture = hud_comp_goal
rgba = [ 128 128 128 30 ]
just = [ center , top ]
Pos = (130, 0)
scale = (1.7, 1.7)
z_priority = 1
rot_angle = -5
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = extra_star_2
Texture = hud_comp_goal
rgba = [ 128 128 128 20 ]
just = [ center , top ]
Pos = (80, -10)
scale = (1.7, 1.7)
z_priority = 1
rot_angle = 10
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = extra_star_3
Texture = hud_comp_goal
rgba = [ 128 128 128 10 ]
just = [ center , top ]
Pos = (15, -25)
scale = (1.6, 1.6)
z_priority = 1
rot_angle = -5
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = pause_dirt
Texture = strip_2
rgba = [ 128 128 128 20 ]
just = [ center , top ]
Pos = (15, -5)
scale = (20, 0.6)
z_priority = 1
rot_angle = 10
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = menu_side_dark1
Texture = roundbar_highlight
rgba = [ 0 0 40 128 ]
just = [ center , center ]
Pos = (530, 210)
scale = (26.2, 21)
z_priority = 1
rot_angle = -10
}
CreateScreenElement {
Type = SpriteElement
parent = current_menu_anchor
id = menu_side_dark2
Texture = roundbar_highlight
rgba = [ 0 0 40 108 ]
just = [ center , center ]
Pos = (530, 210)
scale = (26.2, 21)
z_priority = 1
rot_angle = -10
}
endscript

script paused_title_text
CreateScreenElement { Type = TextElement parent = current_menu_anchor id = paused_text text = "P A U S E D" font = small just = [ right top ] scale = (2.3, 2.6) Pos = (390, 26) rgba = [ 0 0 0 128 ] z_priority = 2 rot_angle = 11 }
endscript

script pause_menu_map_pulse
{ time = 0.3 }
wait ( #2f 0.1 #2e 0.2 #2e 0.3 #2e 0.4 ) seconds
while
DoMorph alpha = 0.0 time = <> time
wait <> time seconds
DoMorph alpha = 1.0 time = <> time
wait ( <> time + 0.1 ) seconds
repeat
endscript

script pause_menu_map
GetLevelStructureName
map_texture = ( <> level_structure_name . level_map )
map_offset = ( <> level_structure_name . map_offset )
map_conversion = ( <> level_structure_name . map_conversion )
map_scale = ( <> level_structure_name . map_scale )
if not GotParam map_texture
return
endif
if IsXenon
AppendSuffixToChecksum Base = <> map_texture SuffixString = "_x"
<> map_texture = <> appended_id
<> scale_adj = ( ( 128.0 / 256.0 ) * ( 0.75 ) )
<> conv_adj = ( 256.0 / 128.0 )
<> map_scale = ( <> map_scale * <> scale_adj )
<> map_conversion = ( <> map_conversion * <> conv_adj )
endif
wait 5 gameframes
while
if IsTextureLoaded id = <> map_texture
break
endif
wait 15 gameframes
repeat
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
scale = <> map_scale
alpha = 0
}
DoScreenElementMorph id = <> id alpha = 1 time = 0.3
map_pos = (200, 200)
CreateScreenElement {
Type = SpriteElement
parent = map_piece_container
id = level_map
Texture = <> map_texture
rgba = [ 128 128 128 128 ]
just = [ center , center ]
Pos = <> map_pos
z_priority = 5
}
skater : Obj_GetPosition
skater : GetHeading
arrow_pos = ( ( <> Pos . (1, 0, 0) ) * (1, 0) + ( <> Pos . (0, 0, 1) ) * (0, 1) )
arrow_pos = ( <> arrow_pos - <> map_offset )
arrow_pos = ( ( <> arrow_pos . (1, 0) * <> map_conversion . (1, 0) ) * (1, 0) + ( <> arrow_pos . (0, 1) * <> map_conversion . (0, 1) ) * (0, 1) )
CreateScreenElement {
Type = SpriteElement
parent = map_piece_container
id = skater_arrow
Texture = Bike_arrow
rgba = [ 123 63 6 108 ]
just = [ center , top ]
Pos = ( <> map_pos + <> arrow_pos )
scale = ( 1.1 / <> map_scale )
z_priority = 40
rot_angle = ( <> heading + 90 )
}
RunScriptOnScreenElement id = skater_arrow pause_menu_map_pulse
CompassManager_DumpPositions
if GotParam blip_array
GetArraySize blip_array
if ( <> array_size > 0 )
index = 0
while
Type = ( ( <> blip_array [ <> index ] ) . Type )
Pos = ( ( <> blip_array [ <> index ] ) . Pos )
Pos = ( <> Pos - <> map_offset )
scaled_pos = ( ( <> Pos . (1, 0) * <> map_conversion . (1, 0) ) * (1, 0) + ( <> Pos . (0, 1) * <> map_conversion . (0, 1) ) * (0, 1) )
rgba = ( compass_bliptypes . <> Type . rgba )
Texture = ( compass_bliptypes . <> Type . Texture )
pulse = ( compass_bliptypes . <> Type . pulse )
z_priority = ( ( compass_bliptypes . <> Type . z_priority ) + 6 )
CreateScreenElement {
Type = SpriteElement
parent = map_piece_container
Texture = <> Texture
rgba = <> rgba
just = [ center , center ]
Pos = ( <> map_pos + <> scaled_pos )
scale = ( 1.0 / <> map_scale )
z_priority = <> z_priority
}
if ( <> pulse = 1 )
RunScriptOnScreenElement id = <> id pause_menu_map_pulse
endif
index = ( <> index + 1 )
repeat <> array_size
endif
endif
endscript

script GetClockText
GetCurrentLevelName
TODManager_GetCurrentTime
ampm = "am"
if ( <> hours > 12 )
ampm = "pm"
hours = ( <> hours - 12 )
endif
if ( <> hours < 10 )
zero_text = "0"
else
zero_text = ""
endif
FormatText TextName = hour_text "%z%h" z = <> zero_text h = <> hours
if ( <> minutes < 10 )
zero_text = "0"
else
zero_text = ""
endif
FormatText TextName = min_text "%z%m" z = <> zero_text m = <> minutes
FormatText TextName = clock_text "%l - %h:%m%p" l = <> level_name h = <> hour_text m = <> min_text p = <> ampm
return clock_text = <> clock_text
endscript

script pause_add_time_and_cash
GetClockText
CreateScreenElement {
Type = TextElement
parent = clock_anchor
id = game_clock
text = <> clock_text
font = dialog
just = [ left , center ]
scale = (0.8, 0.95)
Pos = (80, 12)
rgba = [ 128 128 128 78 ]
z_priority = 20
rot_angle = 8
}
CreateScreenElement {
Type = SpriteElement
parent = clock_anchor
id = time_bar
Texture = goal_grad
rgba = [ 0 0 0 100 ]
just = [ right , top ]
Pos = (285, 18)
scale = (25, 4)
z_priority = 19
rot_angle = 8
}
CareerFunc func = GetCash
FormatText TextName = cash_text "Cash - $%c" c = <> cash
CreateScreenElement {
Type = TextElement
parent = clock_anchor
id = cash_counter
text = <> cash_text
font = dialog
just = [ right , top ]
scale = (0.8, 0.95)
Pos = (210, 26)
rgba = [ 128 128 128 78 ]
z_priority = 20
rot_angle = 4
}
CreateScreenElement {
Type = SpriteElement
parent = clock_anchor
id = cash_bar
Texture = goal_grad
rgba = [ 0 0 0 100 ]
just = [ right , top ]
Pos = (285, 35)
scale = (14, 4)
z_priority = 19
rot_angle = 4
}
endscript

script pause_add_combo_records
CareerFunc func = GetBoardComboRecord
if ( <> board_combo_record > min_career_combo_record )
FormatText TextName = combo_text "High Combo - %c" c = <> board_combo_record UseCommas
CreateScreenElement {
Type = TextElement
parent = clock_anchor
id = high_combo
text = <> combo_text
font = dialog
just = [ left , top ]
scale = (0.8, 0.95)
Pos = (80, 52)
rgba = [ 128 128 128 78 ]
z_priority = 20
rot_angle = 0
}
CreateScreenElement {
Type = SpriteElement
parent = clock_anchor
id = high_combo_bar
Texture = goal_grad
rgba = [ 0 0 0 100 ]
just = [ right , top ]
Pos = (400, 52)
scale = (30, 4)
z_priority = 19
rot_angle = 0
}
endif
if skater : IsSkaterOnBike
CareerFunc func = GetBikeComboRecord
if ( <> bike_combo_record > min_career_combo_record )
FormatText TextName = combo_text "High Bike Combo - %c" c = <> bike_combo_record UseCommas
CreateScreenElement {
Type = TextElement
parent = clock_anchor
id = high_bike__combo
text = <> combo_text
font = dialog
just = [ left , top ]
scale = (0.8, 0.95)
Pos = (80, 78)
rgba = [ 128 128 128 78 ]
z_priority = 20
rot_angle = -4
}
CreateScreenElement {
Type = SpriteElement
parent = clock_anchor
id = high_bike_combo_bar
Texture = goal_grad
rgba = [ 0 0 0 100 ]
just = [ right , top ]
Pos = (400, 64)
scale = (30, 4)
z_priority = 19
rot_angle = -4
}
endif
endif
endscript

script launch_overview_map_menu
SetScreenElementLock id = root_window off
if ObjectExists id = current_menu_anchor
DestroyScreenElement id = current_menu_anchor
endif
CreateScreenElement {
Type = ContainerElement
parent = root_window
id = city_map_anchor
Pos = (0, 0)
dims = (640, 480)
just = [ left top ]
}
AssignAlias id = city_map_anchor alias = current_menu_anchor
create_helper_text helper_text_elements = [ { text = "\\m1 = Back" } ]
SetScreenElementProps {
id = current_menu_anchor
event_handlers = [
{ pad_back city_map_exit }
]
}
white_poly_bg_effect
CreateScreenElement {
Type = ContainerElement
parent = city_map_anchor
id = city_map_parts_anchor
Pos = (0, 0)
dims = (640, 480)
just = [ left top ]
alpha = 0.0
}
CreateScreenElement {
Type = ContainerElement
parent = city_map_parts_anchor
id = map_bg_anchor
Pos = (320, 240)
dims = (640, 480)
just = [ center center ]
scale = ( 0.8 )
}
GetArraySize map_bg_params
index = 0
while
map_add_bg_piece ( map_bg_params [ <> index ] )
index = ( <> index + 1 )
repeat <> array_size
CreateScreenElement {
Type = SpriteElement
parent = map_bg_anchor
Pos = (0, 384)
just = [ left bottom ]
Texture = level_ocean
scale = (8, 3)
rgba = [ 90 90 90 118 ]
z_priority = 5
}
CreateScreenElement {
Type = SpriteElement
parent = map_bg_anchor
Pos = (310, 250)
just = [ center center ]
Texture = level_stain
scale = (5, 4)
rgba = [ 60 60 60 70 ]
z_priority = 200
}
CreateScreenElement {
Type = TextElement
parent = map_bg_anchor
Pos = (390, 170)
just = [ center center ]
font = small
text = "LOS ANGELES"
scale = 2.8
rgba = [ 0 0 0 118 ]
rot_angle = -45
z_priority = 6
}
CreateScreenElement {
Type = TextElement
parent = map_bg_anchor
Pos = (90, 260)
just = [ center center ]
font = small
text = "PACIFIC OCEAN"
scale = 1.6
rgba = [ 128 128 128 60 ]
rot_angle = 60
z_priority = 6
}
GetArraySize map_photo_params
index = 0
while
map_add_level_photo ( map_photo_params [ <> index ] )
index = ( <> index + 1 )
repeat <> array_size
GetArraySize map_connector_params
index = 0
while
map_add_connector ( map_connector_params [ <> index ] )
index = ( <> index + 1 )
repeat <> array_size
DoScreenElementMorph id = city_map_parts_anchor alpha = 1.0 time = 0.5
if ObjectExists id = current_menu_anchor
FireEvent Type = focus target = current_menu_anchor
endif
endscript

script city_map_exit
{ time = 0.3 }
DoScreenElementMorph id = city_map_parts_anchor alpha = 0.0 time = <> time
wait <> time seconds
create_your_options_menu
endscript

script map_add_bg_piece
{ rgba = [ 100 100 100 80 ] }
CreateScreenElement {
Type = SpriteElement
parent = map_bg_anchor
Pos = ( ( <> Pos * 128 ) + (64, 64) )
just = [ center center ]
Texture = <> Texture
rgba = <> rgba
rot_angle = <> rot
<> flip_h
<> flip_v
alpha = <> alpha
z_priority = <> z_priority
scale = <> scale
}
endscript

script map_add_level_photo
CreateScreenElement {
Type = ContainerElement
parent = city_map_parts_anchor
Pos = <> Pos
dims = (200, 200)
just = [ center center ]
z_priority = <> z_priority
rot_angle = <> rot_angle
scale = 0.9
}
container_id = <> id
CreateScreenElement {
Type = SpriteElement
parent = <> container_id
Pos = (0, 0)
just = [ center center ]
Texture = <> photo
scale = 1
rgba = [ 128 128 128 128 ]
}
CreateScreenElement {
Type = SpriteElement
parent = <> container_id
Pos = (2, 4)
just = [ center center ]
Texture = white2
scale = (17, 17)
rgba = [ 0 0 0 108 ]
z_priority = ( <> z_priority -1 )
alpha = 0.4
}
IsLevelUnlocked level = <> level
if ( <> unlocked = 0 )
CreateScreenElement {
Type = SpriteElement
parent = <> container_id
Pos = (0, -5)
just = [ center center ]
Texture = white2
scale = (15, 14)
rgba = [ 0 0 0 128 ]
z_priority = ( <> z_priority + 2 )
}
<> text = "?????????"
endif
CreateScreenElement {
Type = TextElement
parent = <> container_id
Pos = ( (0, 52) + <> text_off )
just = [ center center ]
font = small
text = <> text
scale = 1
rgba = [ 128 128 128 128 ]
z_priority = ( <> z_priority + 23 )
}
black_bar_x_scale = 15
GetScreenElementDims id = <> id
if ( <> width > 120 )
black_bar_x_scale = ( 15 + ( ( <> width -120 ) / 8 ) )
endif
CreateScreenElement {
Type = SpriteElement
parent = <> container_id
Pos = (0, 52)
just = [ center center ]
Texture = white2
scale = ( <> black_bar_x_scale * (1.1, 0) + (0, 2) )
rgba = [ 0 0 0 128 ]
z_priority = ( <> z_priority + 20 )
}
temp = <> level
GetLevelStructureName
RemoveParameter level
level = <> temp
if ( ( <> level_structure_name . load_script ) = <> level )
CreateScreenElement {
Type = SpriteElement
parent = <> container_id
Pos = (0, 0)
just = [ center center ]
Texture = level_x
scale = 1.5
rgba = [ 128 128 128 128 ]
z_priority = ( <> z_priority + 2 )
}
RunScriptOnScreenElement id = <> id city_map_x_pulse_effect
endif
if GotParam tape
switch <> tape
case top_left
tape_pos = (-60, -60)
tape_rot_angle = 45
break case top_right
tape_pos = (60, -60)
tape_rot_angle = -45
break case bottom_left
tape_pos = (-60, 60)
tape_rot_angle = -45
break case bottom_right
tape_pos = (60, 60)
tape_rot_angle = 45
endswitch
CreateScreenElement {
Type = SpriteElement
parent = <> container_id
Pos = <> tape_pos
just = [ center center ]
Texture = level_duct
scale = 1.5
rgba = [ 128 128 128 128 ]
z_priority = ( <> z_priority + 2 )
rot_angle = <> tape_rot_angle
}
endif
if GotParam tape2
switch <> tape2
case top_left
tape_pos = (-60, -60)
tape_rot_angle = 45
break case top_right
tape_pos = (60, -60)
tape_rot_angle = -45
break case bottom_left
tape_pos = (-60, 60)
tape_rot_angle = -45
break case bottom_right
tape_pos = (60, 60)
tape_rot_angle = 45
endswitch
CreateScreenElement {
Type = SpriteElement
parent = <> container_id
Pos = <> tape_pos
just = [ center center ]
Texture = level_duct
scale = 1.5
rgba = [ 128 128 128 128 ]
z_priority = ( <> z_priority + 3 )
rot_angle = <> tape_rot_angle
}
endif
endscript

script city_map_x_pulse_effect
wait 0.1 seconds
while
time = 0.1
#2f DoMorph scale = (1.7, 1.7) alpha = 1.0 relative_scale rot_angle = 3 time = <> time
#2e DoMorph scale = (1.4, 1.4) alpha = 1.0 relative_scale rot_angle = -2 time = <> time
#2e DoMorph scale = (1.5, 1.5) alpha = 1.0 relative_scale rot_angle = -4 time = <> time
#2e DoMorph scale = (1.3, 1.3) alpha = 1.0 relative_scale rot_angle = 4 time = <> time

 DoMorph rot_angle = 0 scale = 1.0 relative_scale alpha = 0.7 time = 0.2
#2f wait 0.1 seconds
#2e wait 0.1 seconds
#2e wait 0.15 seconds

 repeat
endscript

script map_add_connector
CreateScreenElement {
Type = SpriteElement
parent = city_map_parts_anchor
Pos = <> Pos
just = [ center center ]
Texture = level_join
rgba = [ 5 125 10 90 ]
z_priority = 60
rot_angle = <> rot_angle
}
endscript

script pause_menu_legend
DoScreenElementMorph id = pause_vmenu Pos = (800, 75) time = 0.3
if ScreenElementExists id = music_track_anchor
DoScreenElementMorph id = music_track_anchor Pos = (975, 320) time = 0.3
endif
FireEvent Type = unfocus target = pause_vmenu
if ScreenElementExists id = legend_anchor
DestroyScreenElement id = legend_anchor
endif
SetScreenElementLock id = current_menu_anchor off
CreateScreenElement {
Type = ContainerElement
parent = current_menu_anchor
id = legend_anchor
Pos = (720, 110)
just = [ left top ]
event_handlers = [
{ pad_right pause_menu_legend_exit }
{ pad_back pause_menu_legend_exit }
{ pad_start pause_menu_legend_exit }
]
}
CreateScreenElement {
Type = SpriteElement
parent = legend_anchor
Pos = (0, 0)
scale = (75, 57)
Texture = black
rgba = [ 5 5 5 60 ]
z_priority = 100
just = [ left top ]
}
CreateScreenElement {
Type = TextElement
parent = legend_anchor
shadow
shadow_rgba = UI_text_shadow_color
shadow_offs = UI_text_shadow_offset
font = testtitle
text = "LEGEND"
override_encoded_alpha
rgba = [ 9 120 25 128 ]
scale = (1.5, 1.5)
just = [ left top ]
Pos = (180, -20)
z_priority = 110
rot_angle = 4
}
change legend_current_col = 0
change legend_current_row = 0
ForEachIn compass_bliptypes do = legend_add_item
DoScreenElementMorph id = legend_anchor Pos = (320, 110) time = 0.3
SetScreenElementLock id = current_menu_anchor off
create_helper_text {
parent = current_menu_anchor
helper_pos = (330, 426)
helper_text_elements = [
{ text = "\\b5 = Back to Menu" }
]
}
FireEvent Type = focus target = legend_anchor
endscript

script legend_add_item
if GotParam legend_desc
if GotParam own_row
if ( legend_current_col > 0 )
change legend_current_col = 0
change legend_current_row = ( legend_current_row + 1 )
endif
endif
item_pos = ( ( legend_current_col * (140, 0) ) + ( legend_current_row * (0, 31) ) + (20, 20) )
CreateScreenElement {
Type = SpriteElement
parent = legend_anchor
Pos = <> item_pos
Texture = <> Texture
rgba = <> rgba
z_priority = 101
scale = 0.92
}
if ( <> pulse = 1 )
RunScriptOnScreenElement id = <> id pause_menu_map_pulse
endif
CreateScreenElement {
Type = TextElement
parent = legend_anchor
font = dialog
Pos = ( <> item_pos + (20, 0) )
scale = (0.8, 0.95)
rgba = [ 128 128 128 78 ]
z_priority = 101
text = <> legend_desc
just = [ left center ]
}
if GotParam own_row
change legend_current_row = ( legend_current_row + 1 )
else
change legend_current_col = ( legend_current_col + 1 )
if ( legend_current_col > legend_max_col )
change legend_current_col = 0
change legend_current_row = ( legend_current_row + 1 )
endif
endif
endif
endscript

script pause_menu_legend_exit
FireEvent Type = unfocus target = legend_anchor
DoScreenElementMorph id = pause_vmenu Pos = (410, 75) time = 0.3
if ScreenElementExists id = music_track_anchor
DoScreenElementMorph id = music_track_anchor Pos = (575, 320) time = 0.3
endif
DoScreenElementMorph id = legend_anchor Pos = (720, 110) time = 0.3
wait 0.3 seconds
FireEvent Type = focus target = pause_vmenu
SetScreenElementLock id = current_menu_anchor off
create_helper_text {
parent = current_menu_anchor
helper_pos = (330, 426)
helper_text_elements = [
{ text = "\\b6 = Map Legend" }
{ text = "\\b7/\\b4 = Select" }
{ text = "\\m1 = Back" }
{ text = "\\m0 = Accept" }
]
}
endscript

script career_mode_quit_dialog
menu_confirm_quit { yes_script = career_mode_save_dialog }
endscript

script career_mode_save_dialog
<> prompt_save = 1
if GameModeEquals Is_Career
if game_progress_disallow_save
<> prompt_save = 0
endif
endif
if IsXenon
if not CheckForSignIn local
<> prompt_save = 0
endif
endif
if GameModeEquals Is_Career
<> text = "Warning!\\nAny unsaved changes to your current story mode will be lost.\\n\\nDo you wish to save your progress?"
else
<> text = "Warning!\\nAny unsaved changes to your current classic mode will be lost.\\n\\nDo you wish to save your progress?"
endif
if ( <> prompt_save = 1 )
create_error_box {
title = "Save Progress?"
text = <> text
Pos = (310, 240)
just = [ center center ]
text_rgba = [ 88 105 112 128 ]
pad_back_script = career_mode_quit_dialog
buttons = [
{ font = small text = "Yes" pad_choose_script = launch_quit_career_save_game_sequence }
{ font = small text = "No" pad_choose_script = career_quit_to_main }
]
}
else
career_quit_to_main
endif
endscript

script career_quit_to_main
level_select_change_level_quit { level = Load_Z_MainMenu }
endscript
