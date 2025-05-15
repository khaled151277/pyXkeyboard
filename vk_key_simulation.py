# -*- coding: utf-8 -*-
# file: vk_key_simulation.py
# PyXKeyboard v1.0.7 - Key Simulation Logic for VirtualKeyboard
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

try:
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import QTimer
except ImportError:
    print("ERROR: PyQt6 library is required for vk_key_simulation.")
    raise

from . import xlib_integration as xlib_int
from .xlib_integration import X as X_CONST # For X.KeyPress, X.KeyRelease
from .key_definitions import X11_KEYSYM_MAP, FALLBACK_CHAR_MAP
from .settings_manager import DEFAULT_SETTINGS
# Import auto-repeat handlers that are now part of this module's responsibility (or called from here)
from .vk_auto_repeat import handle_key_pressed_for_repeat, handle_key_released_for_repeat


# --- Key Simulation and Modifier Handling ---

def on_modifier_key_press(vk_instance, key_name):
    """ Handles clicks on modifier keys (Shift, Ctrl, Alt, Caps). """
    if vk_instance.repeating_key_name: # Stop any ongoing key repeat
        # Call the simulation-specific release handler
        _handle_key_released_simulation(vk_instance, vk_instance.repeating_key_name, force_stop=True)


    mod_changed = False
    if key_name in ['LShift', 'RShift']:
        vk_instance.shift_pressed = not vk_instance.shift_pressed
        mod_changed = True
    elif key_name in ['L Ctrl', 'R Ctrl']:
        vk_instance.ctrl_pressed = not vk_instance.ctrl_pressed
        mod_changed = True
    elif key_name in ['L Alt', 'R Alt']:
        vk_instance.alt_pressed = not vk_instance.alt_pressed
        mod_changed = True
    elif key_name == 'Caps Lock':
        # Simulate Caps Lock toggle at XTEST level
        sim_success = _send_xtest_key_event(vk_instance, key_name, False, is_caps_toggle=True)
        if sim_success:
            vk_instance.caps_lock_pressed = not vk_instance.caps_lock_pressed
        else:
            QMessageBox.warning(vk_instance, "Caps Lock Error", "Could not toggle system Caps Lock.")
        mod_changed = True

    if mod_changed:
        vk_instance.update_key_labels()


def on_non_repeatable_key_press(vk_instance, key_name):
    """ Handles clicks on non-repeatable keys like Esc, F-keys, Win, App. """
    if vk_instance.repeating_key_name:
        _handle_key_released_simulation(vk_instance, vk_instance.repeating_key_name, force_stop=True)

    # For Win/App keys, Shift/Ctrl/Alt are usually not combined by OSK, so simulate_shift=False
    # For F-keys, Esc etc., they might be combined with Ctrl/Alt/Shift by user intent
    # So, we need to check current sticky modifier states for these.
    effective_shift = vk_instance.shift_pressed if key_name not in ['L Win', 'R Win', 'App'] else False

    sim_ok = _send_xtest_key_event(vk_instance, key_name, simulate_shift=effective_shift)

    released_mods = False
    if sim_ok:
        # For Win/Super and App keys, they typically release other sticky modifiers.
        if key_name in ['L Win', 'R Win', 'App']:
            if vk_instance.ctrl_pressed:
                vk_instance.ctrl_pressed = False; released_mods = True
            if vk_instance.alt_pressed:
                vk_instance.alt_pressed = False; released_mods = True
            if vk_instance.shift_pressed: # Also release shift for these special keys
                vk_instance.shift_pressed = False; released_mods = True
        # For other non-repeatable (like F-keys), if sticky Ctrl/Alt were used, release them. Shift state is maintained.
        elif key_name not in ['LShift', 'RShift', 'Caps Lock']: # Don't auto-release Shift for F-keys etc.
            if vk_instance.ctrl_pressed:
                 vk_instance.ctrl_pressed = False; released_mods = True
            if vk_instance.alt_pressed:
                 vk_instance.alt_pressed = False; released_mods = True


    if released_mods:
        vk_instance.update_key_labels()


def _simulate_single_key_press_event(vk_instance, key_name):
    """Simulates a single press-and-release for a given key name, respecting modifiers."""
    if not key_name: return False

    is_letter = key_name.isalpha() and len(key_name) == 1

    # For arrow keys, Shift is a direct modifier. For letters, it interacts with Caps Lock.
    if key_name in ['Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Page Up', 'Page Down', 'Insert', 'Delete']:
        effective_shift_for_simulation = vk_instance.shift_pressed
    else: # For typable characters, Tab, Enter, Backspace, Space, Esc, F-keys
        effective_shift_for_simulation = (vk_instance.shift_pressed ^ vk_instance.caps_lock_pressed) if is_letter else vk_instance.shift_pressed
    
    sim_ok = _send_xtest_key_event(vk_instance, key_name, effective_shift_for_simulation)
    return sim_ok


def _send_xtest_key_event(vk_instance, key_name, simulate_shift, is_caps_toggle=False):
    """ Sends the low-level XTEST key event sequence. """
    caps_kc = xlib_int.get_caps_lock_keycode()
    shift_kc = xlib_int.get_shift_keycode()
    ctrl_kc = xlib_int.get_ctrl_keycode()
    alt_kc = xlib_int.get_alt_keycode()

    if is_caps_toggle:
        if not xlib_int.is_xtest_ok() or not caps_kc:
            print("XTEST Error: Cannot toggle Caps Lock (XTEST not OK or no CapsLock keycode).")
            return False
        ok = xlib_int.send_xtest_event(X_CONST.KeyPress, caps_kc) and \
             xlib_int.send_xtest_event(X_CONST.KeyRelease, caps_kc)
        if not ok:
            _handle_xtest_error_simulation(vk_instance)
        return ok

    if not xlib_int.is_xtest_ok():
        return False # XTEST not available or failed initialization

    keysym = X11_KEYSYM_MAP.get(key_name)
    if keysym is None or keysym == 0: # 0 is NoSymbol
        print(f"Warning: No (or invalid) X11 KeySym defined for '{key_name}'. Cannot simulate.")
        return False

    keycode = xlib_int.keysym_to_keycode(keysym)
    if not keycode: # If keysym_to_keycode returns None (or 0, which it treats as None)
        print(f"WARNING: No KeyCode found for KeySym {hex(keysym)} ('{key_name}'). Cannot simulate.")
        return False

    # Determine which modifiers need to be pressed for this event
    press_shift_for_event = simulate_shift and shift_kc
    press_ctrl_for_event = vk_instance.ctrl_pressed and ctrl_kc
    press_alt_for_event = vk_instance.alt_pressed and alt_kc

    all_ok = True
    try:
        # Press modifiers
        if press_ctrl_for_event: all_ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, ctrl_kc)
        if press_alt_for_event: all_ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, alt_kc)
        if press_shift_for_event: all_ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, shift_kc)
        if not all_ok: raise Exception("Modifier Press Failure")

        # Press and release the main key
        all_ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, keycode)
        all_ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, keycode)
        if not all_ok: raise Exception("Main Key Press/Release Failure")

        # Release modifiers (in reverse order of press ideally, though often not critical for XTEST)
        if press_shift_for_event: all_ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, shift_kc)
        if press_alt_for_event: all_ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, alt_kc)
        if press_ctrl_for_event: all_ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, ctrl_kc)
        if not all_ok: raise Exception("Modifier Release Failure")

        return True

    except Exception as e:
        print(f"ERROR during XTEST sequence for '{key_name}': {e}")
        _handle_xtest_error_simulation(vk_instance, critical=True) # Assume critical if sequence fails
        # Attempt to clean up any pressed modifiers if an error occurred mid-sequence
        try:
            # Use the actual state of whether they were pressed for *this event*
            if press_shift_for_event and xlib_int.is_xtest_ok() and shift_kc:
                xlib_int.send_xtest_event(X_CONST.KeyRelease, shift_kc)
            if press_alt_for_event and xlib_int.is_xtest_ok() and alt_kc:
                xlib_int.send_xtest_event(X_CONST.KeyRelease, alt_kc)
            if press_ctrl_for_event and xlib_int.is_xtest_ok() and ctrl_kc:
                xlib_int.send_xtest_event(X_CONST.KeyRelease, ctrl_kc)
            if xlib_int.is_xtest_ok():
                 xlib_int.flush_display()
        except Exception:
            pass # Avoid error during cleanup
        return False


def _handle_xtest_error_simulation(vk_instance, critical=False):
    """Handles XTEST errors, potentially disabling XTEST and notifying user."""
    if xlib_int.is_xtest_ok(): # Only act if it was previously considered OK
        # To actually disable, the flag in xlib_integration should be set.
        # This function mostly handles the GUI feedback part.
        # xlib_int._xlib_ok = False # Let xlib_integration manage its own state.
        print("XTEST operation failed. Subsequent XTEST calls might also fail.")
        if xlib_int.get_display(): # Check if display object exists before flushing
            xlib_int.flush_display() 
        
        msg_title = "XTEST Error"
        msg_text = "A key simulation error occurred."
        if critical:
            msg_text += "\nXTEST (key input) functionality might be compromised."
        
        QMessageBox.warning(vk_instance, msg_title, msg_text)
        vk_instance.xlib_ok = xlib_int.is_xtest_ok() # Re-check status from xlib_int
        vk_instance.init_tray_icon() # Update tray icon tooltip if status changes


def on_typable_key_right_press(vk_instance, key_name):
    """ Handles right-click on typable keys: Simulates Shift + Key and flashes button. """
    print(f"Right-click detected on typable key: {key_name}")
    if vk_instance.repeating_key_name:
        _handle_key_released_simulation(vk_instance, vk_instance.repeating_key_name, force_stop=True)

    button = vk_instance.buttons.get(key_name)
    if not button: return

    # Determine the shifted character for display purposes
    active_layout_map = vk_instance.loaded_layouts.get(vk_instance.current_language)
    fallback_map_to_use = vk_instance.loaded_layouts.get('us',
                            vk_instance.loaded_layouts.get('en',
                                FALLBACK_CHAR_MAP if isinstance(FALLBACK_CHAR_MAP, dict) else {}
                            ))
    if active_layout_map is None: active_layout_map = fallback_map_to_use
    char_tuple = active_layout_map.get(key_name, fallback_map_to_use.get(key_name))

    shifted_char_for_display = None
    if char_tuple and isinstance(char_tuple, (list, tuple)) and len(char_tuple) > 1:
        shifted_char_for_display = char_tuple[1] # This could be None if JSON has `null`

    # Simulate Shift + Key press. Ctrl/Alt are NOT applied with right-click shift.
    # Store current Ctrl/Alt state, simulate, then restore.
    temp_ctrl_pressed = vk_instance.ctrl_pressed
    temp_alt_pressed = vk_instance.alt_pressed
    vk_instance.ctrl_pressed = False
    vk_instance.alt_pressed = False

    sim_ok = _send_xtest_key_event(vk_instance, key_name, simulate_shift=True)

    vk_instance.ctrl_pressed = temp_ctrl_pressed # Restore Ctrl
    vk_instance.alt_pressed = temp_alt_pressed   # Restore Alt


    original_stylesheet = button.styleSheet() # Save original style for restoring
    if sim_ok and shifted_char_for_display is not None: # Only flash if simulation worked and we have a char to show
        try:
            button.setText(shifted_char_for_display) # Temporarily set text to shifted char
            flash_style = "background-color: #ADD8E6 !important; color: black !important; font-weight: bold;"
            button.setStyleSheet(original_stylesheet + flash_style) # Append flash style
            # Restore after a delay
            QTimer.singleShot(300, lambda: vk_instance._revert_button_flash(button, original_stylesheet))
        except Exception as e:
            print(f"Error flashing button for right-click: {e}")
            vk_instance._revert_button_flash(button, original_stylesheet) # Ensure revert on error

    # Right-click shift should release any *other* sticky modifiers like Ctrl, Alt,
    # but not Shift itself (as it was just used for this action).
    # The Shift state of the keyboard (vk_instance.shift_pressed) should remain unchanged
    # by a right-click action itself.
    released_other_mods = False
    if sim_ok: # If simulation was successful
        if vk_instance.ctrl_pressed:
            vk_instance.ctrl_pressed = False; released_other_mods = True
        if vk_instance.alt_pressed:
            vk_instance.alt_pressed = False; released_other_mods = True
    
    if released_other_mods:
        # Delay label update slightly to allow flash to be visible
        QTimer.singleShot(310, vk_instance.update_key_labels)


def _handle_key_pressed_simulation(vk_instance, key_name):
    """
    Handles the initial press of a potentially repeating key.
    Simulates the first key event, then starts auto-repeat if enabled.
    """
    # If another key is already repeating, stop it
    if vk_instance.repeating_key_name and vk_instance.repeating_key_name != key_name:
        _handle_key_released_simulation(vk_instance, vk_instance.repeating_key_name, force_stop=True)

    sim_ok = vk_instance._simulate_single_key_press_event(key_name)

    # Determine if sticky modifiers should be released AFTER this key press
    # Typable characters and Space usually release Shift/Ctrl/Alt
    # Functional repeatable keys (Backspace, Enter, Arrows, Tab, Del) DO NOT release sticky mods.
    should_release_sticky_mods = key_name in FALLBACK_CHAR_MAP or key_name == 'Space'

    released_mods = False
    if sim_ok and should_release_sticky_mods:
        if vk_instance.shift_pressed:
            vk_instance.shift_pressed = False
            released_mods = True
        if vk_instance.ctrl_pressed:
            vk_instance.ctrl_pressed = False
            released_mods = True
        if vk_instance.alt_pressed:
            vk_instance.alt_pressed = False
            released_mods = True

    if released_mods:
        vk_instance.update_key_labels() # Update labels if modifiers changed

    # If simulation was successful and auto-repeat is enabled, start the timers
    if sim_ok: # Pass vk_instance to the auto-repeat handler
        handle_key_pressed_for_repeat(vk_instance, key_name)


def _handle_key_released_simulation(vk_instance, key_name, force_stop=False):
    """
    Handles the release of a potentially repeating key.
    Mainly calls the auto-repeat handler to stop timers.
    """
    # Pass vk_instance to the auto-repeat handler
    handle_key_released_for_repeat(vk_instance, key_name, force_stop=force_stop)
