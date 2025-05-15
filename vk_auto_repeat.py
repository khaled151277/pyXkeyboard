# -*- coding: utf-8 -*-
# file: vk_auto_repeat.py
# PyXKeyboard v1.0.7 - Key Auto-Repeat Logic for VirtualKeyboard
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

try:
    from PyQt6.QtCore import QTimer
except ImportError:
    print("ERROR: PyQt6 library is required for vk_auto_repeat.")
    raise

from .settings_manager import DEFAULT_SETTINGS
# Import the key simulation function directly if needed, or pass vk_instance
# from .vk_key_simulation import _simulate_single_key_press_event (Causes circular import if not careful)

# --- Key Auto-Repeat Handling ---

def update_repeat_timers_from_settings(vk_instance):
    """Updates the intervals of the auto-repeat timers based on current settings."""
    delay_ms = vk_instance.settings.get("auto_repeat_delay_ms", DEFAULT_SETTINGS.get("auto_repeat_delay_ms", 1500))
    interval_ms = vk_instance.settings.get("auto_repeat_interval_ms", DEFAULT_SETTINGS.get("auto_repeat_interval_ms", 100))

    vk_instance.initial_delay_timer.setInterval(delay_ms)
    vk_instance.auto_repeat_timer.setInterval(interval_ms)

def handle_key_pressed_for_repeat(vk_instance, key_name):
    """
    Handles the initial press of a potentially repeating key.
    This function is called from vk_key_simulation._handle_key_pressed_simulation
    after the first key event has been simulated.
    """
    if vk_instance.settings.get("auto_repeat_enabled", DEFAULT_SETTINGS.get("auto_repeat_enabled", True)):
        vk_instance.repeating_key_name = key_name
        vk_instance.initial_delay_timer.start()

def handle_key_released_for_repeat(vk_instance, key_name, force_stop=False):
    """
    Handles the release of a potentially repeating key.
    Stops the auto-repeat timers.
    """
    if force_stop or (vk_instance.repeating_key_name == key_name):
        if vk_instance.repeating_key_name: # Check if a key was actually repeating
            vk_instance.initial_delay_timer.stop()
            vk_instance.auto_repeat_timer.stop()
            vk_instance.repeating_key_name = None # Clear the repeating key

def trigger_initial_repeat(vk_instance):
    """
    Called after the initial delay by initial_delay_timer.
    Simulates the key press again and starts the subsequent repeat timer.
    """
    if vk_instance.repeating_key_name:
        # The key simulation needs to happen here.
        # It's better to call a method on vk_instance that handles the simulation.
        sim_ok = vk_instance._simulate_single_key_press_event(vk_instance.repeating_key_name)

        if sim_ok:
            vk_instance.auto_repeat_timer.start()
        else:
            # If simulation fails (e.g., XTEST error), stop repeating.
            handle_key_released_for_repeat(vk_instance, vk_instance.repeating_key_name, force_stop=True)
    else:
        # Safety stop if no key is marked for repeat (should not happen if logic is correct)
        vk_instance.initial_delay_timer.stop()
        vk_instance.auto_repeat_timer.stop()


def trigger_subsequent_repeat(vk_instance):
    """
    Called by the auto_repeat_timer for each subsequent repeat action.
    Simulates the key press.
    """
    if vk_instance.repeating_key_name:
        # Simulate the key press
        sim_ok = vk_instance._simulate_single_key_press_event(vk_instance.repeating_key_name)

        if not sim_ok:
            # If simulation fails, stop repeating this key.
            handle_key_released_for_repeat(vk_instance, vk_instance.repeating_key_name, force_stop=True)
    else:
        # Safety stop if no key is marked for repeat
        vk_instance.auto_repeat_timer.stop()

# Add to vk_key_simulation.py, replacing existing _handle_key_pressed and _handle_key_released

def _handle_key_pressed_simulation(vk_instance, key_name):
    """
    Handles the initial press of a potentially repeating key.
    Simulates the first key event, then starts auto-repeat if enabled.
    """
    from .key_definitions import FALLBACK_CHAR_MAP # Local import to avoid cycle at module level

    # If another key is already repeating, stop it
    if vk_instance.repeating_key_name and vk_instance.repeating_key_name != key_name:
        handle_key_released_for_repeat(vk_instance, vk_instance.repeating_key_name, force_stop=True)

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
    if sim_ok:
        handle_key_pressed_for_repeat(vk_instance, key_name)


def _handle_key_released_simulation(vk_instance, key_name, force_stop=False):
    """
    Handles the release of a potentially repeating key.
    Mainly calls the auto-repeat handler to stop timers.
    """
    handle_key_released_for_repeat(vk_instance, key_name, force_stop=force_stop)
