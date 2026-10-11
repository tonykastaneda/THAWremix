; THAW's pause menu look on Remix (tools/thawui.py compiles this into gamemenu_pause.qb):
; Remix's create_pause_menu with its own items, conditions and handlers, built as THAW's tilted label
; menu (make_label_menu at THAW's (410, 75), add_label_menu_item with THAW's scale 0.85 and its
; tilt / offset pattern, label_menu_finish), and THAW's background effect and P A U S E D title in
; place of THUG2's yellow sign and side gradient. Generated from both games' scripts, then kept.

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
make_label_menu {
menu_id = pause_menu
vmenu_id = pause_vmenu
pad_back_script = NullScript
Pos = (410, 75)
spacing = 0
}
else
make_label_menu {
menu_id = pause_menu
vmenu_id = pause_vmenu
pad_back_script = handle_start_pressed
Pos = (410, 75)
spacing = 0
}
endif
paused_title_text
kill_start_key_binding
white_poly_bg_effect
; THAW's area map on the left, in story mode in Hollywood (tools/ui/pausemap.q)
if GameModeEquals Is_Career
if LevelIs load_tr
RunScriptOnScreenElement id = current_menu_anchor hw_pause_map
endif
endif
add_music_track_text Pos = (575, 320)
if GameModeEquals Is_SingleSession
add_label_menu_item { scale = 0.85 rot = 0 label_offset = (-20, 0) text = "CONTINUE"
id = menu_continue
pad_choose_script = handle_pause_continue
pad_choose_sound = generic_pause_exit_sound
}
if GoalManager_GoalIsActive Name = trickattack
add_label_menu_item { scale = 0.85 rot = 4 label_offset = (-10, 0)
text = "RETRY HIGH SCORE RUN"
id = menu_retry_high_score_run
pad_choose_script = menu_select
pad_choose_params = { stop_streams menu_select_script = RetryCurrentGoal }
}
add_label_menu_item { scale = 0.85 rot = -2 label_offset = (-40, 0)
text = "END HIGH SCORE RUN"
id = menu_end_high_score_run
pad_choose_script = menu_select
pad_choose_params = { menu_select_script = end_high_score_run }
}
else
add_label_menu_item { scale = 0.85 rot = -5 label_offset = (-20, 0)
text = "START HIGH SCORE RUN"
id = menu_start_high_score_run
pad_choose_script = menu_select
pad_choose_params = { menu_select_script = TrickAttack_MenuStartRun }
}
endif
else
if not GotParam no_exit
add_label_menu_item { scale = 0.85 rot = -2 label_offset = (-30, 0) text = "CONTINUE"
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
add_label_menu_item text = "RETRY LAST GOAL" id = menu_retry_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration menu_select_script = RetryCurrentGoal } scale = 0.85 rot = -2 label_offset = (-10, 0)
endif
endif
endif
endif
endif
add_label_menu_item text = "VIEW GOALS" id = menu_view_goals pad_choose_script = create_view_selected_goals_menu pad_choose_params = { from_pause } scale = 0.85 rot = 2 label_offset = (-20, 0)
endif
if GameModeEquals Is_Career
goal_id = ( 0xf656454b )
if not ChecksumEquals a = <> goal_id b = null
if GoalManager_GoalExists Name = <> goal_id
if GoalManager_GoalIsActive Name = <> goal_id
add_label_menu_item text = "END CURRENT RUN" id = 0x51d383fc pad_choose_script = 0x2825beb0 pad_choose_params = { goal_id = <> goal_id } scale = 0.85 rot = -4 label_offset = (-30, 0)
endif
endif
endif
if GoalManager_CanRetryGoal
add_label_menu_item text = "RETRY LAST GOAL" id = menu_retry_goal pad_choose_script = menu_select pad_choose_params = { stop_vibration stop_streams menu_select_script = RetryCurrentGoal } scale = 0.85 rot = 0 label_offset = (-20, 0)
endif
if not LevelIs load_se
add_label_menu_item text = "VIEW GOALS" id = menu_chapters pad_choose_script = view_goals_menu_create scale = 0.85 rot = 4 label_offset = (-10, 0)
endif
add_label_menu_item text = "TEXT MESSAGES" id = menu_pager pad_choose_script = pager_window_create scale = 0.85 rot = -2 label_offset = (-40, 0)
else
if GameModeEquals 0x353961d7
if GoalManager_HasActiveGoals
add_label_menu_item text = "END CURRENT GOAL" id = 0x301fe103 pad_choose_script = menu_select pad_choose_params = { menu_select_script = end_current_goal_run } scale = 0.85 rot = -5 label_offset = (-20, 0)
endif
add_label_menu_item text = "VIEW GOALS" id = menu_view_goals pad_choose_script = view_created_goals_menu_create scale = 0.85 rot = -2 label_offset = (-30, 0)
if not LevelIs load_sk5ed_gameplay
add_label_menu_item text = "CREATE A GOAL" id = 0x760c05ab pad_choose_script = 0x7f920ac4 scale = 0.85 rot = -2 label_offset = (-10, 0)
endif
endif
endif
if GameModeEquals is_classic
classic_mode_menu_add_pause_options
endif
if GameModeEquals 0x353961d7
if not LevelIs load_sk5ed_gameplay
add_label_menu_item text = "LOAD GOALS" id = 0xeabf1213 pad_choose_script = 0xe37d24e6 scale = 0.85 rot = 2 label_offset = (-20, 0)
0x81f01058 : 0x96874358 0xb99f6330
if ( <> 0x54809825 = 0 )
0xb8bfaeed = 1
endif
add_label_menu_item text = "SAVE GOALS" id = 0x24d12062 pad_choose_script = launch_pause_menu_save_created_goals not_focusable = <> 0xb8bfaeed scale = 0.85 rot = -4 label_offset = (-30, 0)
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
add_label_menu_item { scale = 0.85 rot = 0 label_offset = (-20, 0) text = "CHANGE LEVEL"
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
add_label_menu_item text = "START GAME" id = menu_network_start_select pad_choose_script = network_game_options_selected scale = 0.85 rot = 4 label_offset = (-10, 0)
endif
endif
else
add_label_menu_item text = "END CURRENT GAME" id = menu_network_end_select pad_choose_script = network_end_game_selected scale = 0.85 rot = -2 label_offset = (-40, 0)
endif
endif
endif
if InNetGame
if not NetworkGamePending
if OnServer
if OnXbox
add_label_menu_item text = "HOST OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected scale = 0.85 rot = -5 label_offset = (-20, 0)
else
add_label_menu_item text = "SERVER OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected scale = 0.85 rot = -2 label_offset = (-30, 0)
endif
endif
if IsHost
if GameModeEquals is_lobby
if not OnServer
if OnXbox
add_label_menu_item text = "HOST OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected scale = 0.85 rot = -2 label_offset = (-10, 0)
else
add_label_menu_item text = "SERVER OPTIONS" id = menu_network_server_opts_select pad_choose_script = network_options_selected scale = 0.85 rot = 2 label_offset = (-20, 0)
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
add_label_menu_item text = <> trick_text id = menu_cas pad_choose_script = create_edit_tricks_menu scale = 0.85 rot = -4 label_offset = (-30, 0)
endif
endif
if InNetGame
if IsHost
if GameModeEquals is_lobby
if not NetworkGamePending
if not ChangeLevelPending
add_label_menu_item text = "CHANGE LEVEL" id = menu_level_select pad_choose_script = launch_level_select_menu pad_choose_params = { show_warning } scale = 0.85 rot = 0 label_offset = (-20, 0)
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
add_label_menu_item text = "CHANGE PRO" id = 0x64c3ffcf pad_choose_script = 0x333166cf <> 0x194e4159 scale = 0.85 rot = 4 label_offset = (-10, 0)
endif
endif
endif
endif
if not InNetGame
add_label_menu_item text = "YOUR OPTIONS" id = menu_your_options pad_choose_script = create_your_options_menu scale = 0.85 rot = -2 label_offset = (-40, 0)
endif
add_label_menu_item text = "GAME OPTIONS" id = menu_game_options pad_choose_script = create_options_menu scale = 0.85 rot = -5 label_offset = (-20, 0)
if not CD
add_label_menu_item text = "DEBUG OPTIONS" id = debug_menu pad_choose_script = create_debug_options_menu scale = 0.85 rot = -2 label_offset = (-30, 0)
endif
if not CD
if ( main_menu_jump_to_cas = 1 )
add_label_menu_item text = "BACK TO CAS" id = debug_cas_menu pad_choose_script = create_pre_cas_menu pad_choose_params = { load_assets = 1 } scale = 0.85 rot = -2 label_offset = (-10, 0)
endif
endif
if InNetGame
if not OnServer
if not IsObserving
if InInternetMode
if IsTrue Bootstrap_Build
if not GoalManager_HasActiveGoals
add_label_menu_item text = "OBSERVE" id = menu_network_observe_select pad_choose_script = chose_observe not_focusable = not_focusable scale = 0.85 rot = 2 label_offset = (-20, 0)
endif
else
if not GoalManager_HasActiveGoals
add_label_menu_item text = "OBSERVE" id = menu_network_observe_select pad_choose_script = chose_observe scale = 0.85 rot = -4 label_offset = (-30, 0)
endif
endif
endif
endif
endif
add_label_menu_item text = "QUIT" id = menu_quit pad_choose_script = generic_menu_pad_choose pad_choose_params = { callback = launch_quit_game_dialog } scale = 0.85 rot = 0 label_offset = (-20, 0)
else
if CustomParkMode testing
printf "PARK EDITOR TEST PLAY MENU"
add_label_menu_item text = "BACK TO EDITOR" id = menu_skateshop pad_choose_script = menu_confirm_quit pad_choose_params = { yes_script = exit_test_play } scale = 0.85 rot = 4 label_offset = (-10, 0)
else
if GameModeEquals is_classic
classic_mode_menu_add_quit_option
else
add_label_menu_item { scale = 0.85 rot = -2 label_offset = (-40, 0) text = "QUIT"
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
label_menu_finish helper_text = <> helper data = <> focus_data
; THUG2's yellow PAUSED sign (a theme piece build_pause_menu_parts brings in) stays out
if ScreenElementExists id = paused_piece
DoScreenElementMorph id = paused_piece alpha = 0 time = 0
endif
endscript

; THAW (gamemenu_pause): the pause backdrop, minus the stars (hud_comp_goal) and dirt strip
; (strip_2), which Remix has no textures for
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
; rot_angle on the text element itself (THAW's way) crashes a real PSP: Remix's text drawing reads a
; null string for rotated text. The tilt goes on a container instead, as the label menu does it.
CreateScreenElement { Type = ContainerElement parent = current_menu_anchor id = paused_text_anchor Pos = (395, 78) just = [ right top ] rot_angle = 11 }
CreateScreenElement { Type = TextElement parent = paused_text_anchor id = paused_text text = 'P A U S E D' font = small just = [ right top ] scale = (2.3, 2.6) Pos = (0, 0) rgba = [ 0 0 0 128 ] z_priority = 2 }
endscript
