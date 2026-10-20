script create_pause_menu
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
hide_all_hud_items
unhide_current_goal
if InNetGame
if not IsObserving
skater : NetDisablePlayerInput
endif
else
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
create_mp_pause_menu
PauseMusicAndStreams 1
build_pause_menu_parts
return
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
if ( in_cat_preview_mode = 1 )
create_CAT_pause_menu
return
endif
if not GotParam no_exit
helper = generic_helper_text
else
helper = generic_helper_text_no_back
endif
if GotParam no_exit
make_new_roundbar_menu {
menu_id = pause_menu
vmenu_id = pause_vmenu
pad_back_script = NullScript
Pos = (250, 95)
dims = (250, 480)
internal_text_just = right
helper_text = <> helper
add_3d_bg
}
else
make_new_roundbar_menu {
menu_id = pause_menu
vmenu_id = pause_vmenu
pad_back_script = handle_start_pressed
Pos = (250, 95)
dims = (250, 480)
internal_text_just = right
helper_text = <> helper
add_3d_bg
}
endif
do_localized_pause_title Pos = (500, 95)
kill_start_key_binding
pause_menu_gradient right
add_music_track_text Pos = (575, 320)
if GameModeEquals Is_SingleSession
add_roundbar_menu_item { text = "CONTINUE"
id = menu_continue
pad_choose_script = handle_pause_continue
pad_choose_sound = generic_pause_exit_sound
}
if GoalManager_GoalIsActive Name = trickattack
add_roundbar_menu_item {
text = "RETRY HIGH SCORE RUN"
id = menu_retry_high_score_run
pad_choose_script = menu_select
pad_choose_params = { stop_streams menu_select_script = RetryCurrentGoal }
}
add_roundbar_menu_item {
text = "END HIGH SCORE RUN"
id = menu_end_high_score_run
pad_choose_script = menu_select
pad_choose_params = { menu_select_script = end_high_score_run }
}
else
add_roundbar_menu_item {
text = "START HIGH SCORE RUN"
id = menu_start_high_score_run
pad_choose_script = menu_select
pad_choose_params = { menu_select_script = TrickAttack_MenuStartRun }
}
endif
else
if not GotParam no_exit
add_roundbar_menu_item { text = "CONTINUE"
id = menu_continue
pad_choose_script = handle_pause_continue
pad_choose_sound = generic_pause_exit_sound
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
add_roundbar_menu_item text = "RETRY LAST GOAL" id = menu_retry_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration menu_select_script = RetryCurrentGoal }
endif
endif
endif
endif
endif
add_roundbar_menu_item text = "VIEW GOALS" id = menu_view_goals pad_choose_script = create_view_selected_goals_menu pad_choose_params = { from_pause }
endif
if GameModeEquals Is_Career
goal_id = ( 0xf656454b )
if not ChecksumEquals a = <> goal_id b = null
if GoalManager_GoalExists Name = <> goal_id
if GoalManager_GoalIsActive Name = <> goal_id
add_roundbar_menu_item text = "END CURRENT RUN" id = 0x51d383fc pad_choose_script = 0x2825beb0 pad_choose_params = { goal_id = <> goal_id }
endif
endif
endif
if GoalManager_CanRetryGoal
add_roundbar_menu_item text = "RETRY LAST GOAL" id = menu_retry_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration stop_streams menu_select_script = RetryCurrentGoal }
endif
if not LevelIs load_se
add_roundbar_menu_item text = "VIEW GOALS" id = menu_chapters pad_choose_script = view_goals_menu_create
endif
add_roundbar_menu_item text = "TEXT MESSAGES" id = menu_pager pad_choose_script = pager_window_create
else
if GameModeEquals 0x353961d7
if GoalManager_HasActiveGoals
add_roundbar_menu_item text = "END CURRENT GOAL" id = 0x301fe103 pad_choose_script = menu_select pad_choose_params = { menu_select_script = end_current_goal_run }
endif
add_roundbar_menu_item text = "VIEW GOALS" id = menu_view_goals pad_choose_script = view_created_goals_menu_create
if not LevelIs load_sk5ed_gameplay
add_roundbar_menu_item text = "CREATE A GOAL" id = 0x760c05ab pad_choose_script = 0x7f920ac4
endif
endif
endif
if GameModeEquals is_classic
classic_mode_menu_add_pause_options
endif
if GameModeEquals 0x353961d7
if not LevelIs load_sk5ed_gameplay
add_roundbar_menu_item text = "LOAD GOALS" id = 0xeabf1213 pad_choose_script = 0xe37d24e6
0x81f01058 : 0x96874358 0xb99f6330
if ( <> 0x54809825 = 0 )
0xb8bfaeed = 1
endif
add_roundbar_menu_item text = "SAVE GOALS" id = 0x24d12062 pad_choose_script = launch_pause_menu_save_created_goals not_focusable = <> 0xb8bfaeed
endif
endif
display_level_select = 1
if InNetGame
display_level_select = 0
endif
if GameModeEquals is_classic
if not GotParam no_exit
display_level_select = 0
endif
endif
if ( <> display_level_select = 1 )
add_roundbar_menu_item { text = "CHANGE LEVEL"
id = menu_level_select
pad_choose_script = launch_level_select_menu
tag_grid_x = 1
}
endif
if InNetGame
if IsHost
if GameModeEquals is_lobby
if not NetworkGamePending
if not ChangeLevelPending
add_roundbar_menu_item text = "START GAME" id = menu_network_start_select pad_choose_script = network_game_options_selected
endif
endif
else
add_roundbar_menu_item text = "END CURRENT GAME" id = menu_network_end_select pad_choose_script = network_end_game_selected
endif
endif
endif
if InNetGame
if not NetworkGamePending
if OnServer
if OnXbox
add_roundbar_menu_item text = "HOST OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected
else
add_roundbar_menu_item text = "SERVER OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected
endif
endif
if IsHost
if GameModeEquals is_lobby
if not OnServer
if OnXbox
add_roundbar_menu_item text = "HOST OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected
else
add_roundbar_menu_item text = "SERVER OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected
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
add_roundbar_menu_item text = <> trick_text id = menu_cas pad_choose_script = create_edit_tricks_menu
endif
endif
if InNetGame
if IsHost
if GameModeEquals is_lobby
if not NetworkGamePending
if not ChangeLevelPending
add_roundbar_menu_item text = "CHANGE LEVEL" id = menu_level_select pad_choose_script = launch_level_select_menu pad_choose_params = { show_warning }
endif
endif
endif
endif
if not OnXbox
endif
endif
if not InNetGame
if GameModeEquals Is_Career
0x414b3429
if ( <> 0xc3254e71 > 1 )
GetCurrentSkaterProfileIndex
GetSkaterProfileInfo player = <> currentSkaterProfileIndex
if ChecksumEquals a = <> skater_family b = family_pro
if skater : IsInBail
0x194e4159 = not_focusable
else
0x194e4159 = { }
endif
add_roundbar_menu_item text = "CHANGE PRO" id = 0x64c3ffcf pad_choose_script = 0x333166cf <> 0x194e4159
endif
endif
endif
endif
if not InNetGame
add_roundbar_menu_item text = "YOUR OPTIONS" id = menu_your_options pad_choose_script = create_your_options_menu
endif
add_roundbar_menu_item text = "GAME OPTIONS" id = menu_game_options pad_choose_script = create_options_menu
if not CD
add_roundbar_menu_item text = "DEBUG OPTIONS" id = debug_menu pad_choose_script = create_debug_options_menu
endif
if not CD
if ( main_menu_jump_to_cas = 1 )
add_roundbar_menu_item text = "BACK TO CAS" id = debug_cas_menu pad_choose_script = create_pre_cas_menu pad_choose_params = { load_assets = 1 }
endif
endif
if InNetGame
if not OnServer
if not IsObserving
if InInternetMode
if IsTrue Bootstrap_Build
if not GoalManager_HasActiveGoals
add_roundbar_menu_item text = "OBSERVE" id = menu_network_observe_select pad_choose_script = chose_observe not_focusable = not_focusable
endif
else
if not GoalManager_HasActiveGoals
add_roundbar_menu_item text = "OBSERVE" id = menu_network_observe_select pad_choose_script = chose_observe
endif
endif
endif
endif
endif
add_roundbar_menu_item text = "QUIT" id = menu_quit pad_choose_script = generic_menu_pad_choose pad_choose_params = { callback = launch_quit_game_dialog }
else
if CustomParkMode testing
printf "PARK EDITOR TEST PLAY MENU"
add_roundbar_menu_item text = "BACK TO EDITOR" id = menu_skateshop pad_choose_script = menu_confirm_quit pad_choose_params = { yes_script = exit_test_play }
else
if GameModeEquals is_classic
classic_mode_menu_add_quit_option
else
add_roundbar_menu_item { text = "QUIT"
id = menu_skateshop
pad_choose_script = generic_menu_pad_choose
pad_choose_params = { callback = menu_confirm_quit }
tip_text = "Seeya!"
}
endif
endif
endif
kill_blur Start = 0
if root_window : GetSingleTag highlight_change_level
focus_data = { grid_index = 1 }
root_window : RemoveTags tags = [ highlight_change_level ]
endif
roundbar_menu_finish show_deck = show_deck data = <> focus_data
endscript