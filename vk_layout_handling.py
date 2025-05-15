# -*- coding: utf-8 -*-
# file: vk_layout_handling.py
# PyXKeyboard v1.0.7 - Layout Management for VirtualKeyboard
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

import os
import json
from typing import Optional, Dict, List, Union

try:
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import QTimer, Qt
except ImportError:
    print("ERROR: PyQt6 library is required for vk_layout_handling.")
    raise

from .XKB_Switcher import XKBManager, XKBManagerError
from .key_definitions import FALLBACK_CHAR_MAP


def init_xkb_manager_and_layouts(vk_instance):
    """Initializes the XKBManager, loads corresponding layouts, and starts monitoring/timer."""
    vk_instance.xkb_manager = None # Reset
    if vk_instance.layout_check_timer and vk_instance.layout_check_timer.isActive():
        vk_instance.layout_check_timer.stop()
    vk_instance.layout_check_timer = None

    system_layouts = []
    try:
        vk_instance.xkb_manager = XKBManager(auto_refresh=True, start_monitoring=False) # auto_refresh loads initial list

        if vk_instance.xkb_manager and vk_instance.xkb_manager.get_current_method() != XKBManager.METHOD_NONE:
            system_layouts = vk_instance.xkb_manager.get_available_layouts()
            print(f"System layouts detected by XKBManager: {system_layouts}")

            # Load layout files corresponding to system layouts
            load_layout_files_from_system_config(vk_instance, system_layouts)

            # Connect signal for layout changes
            vk_instance.xkb_manager.layoutChanged.connect(
                vk_instance.sync_vk_lang_with_system_slot,
                Qt.ConnectionType.QueuedConnection
            )

            # Start monitoring if possible, otherwise use a timer
            if vk_instance.xkb_manager.can_monitor():
                print("Starting xkb-switch monitoring for layout changes...")
                vk_instance.xkb_manager.start_change_monitor()
            else:
                print("xkb-switch monitoring not available or failed, starting fallback polling timer...")
                vk_instance.layout_check_timer = QTimer(vk_instance)
                vk_instance.layout_check_timer.timeout.connect(vk_instance.check_system_layout_timer_slot)
                vk_instance.layout_check_timer.start(1000) # Check every second
        else:
            print("XKB Manager could not be initialized with any method. Loading default layouts only.")
            load_layout_files_from_system_config(vk_instance, ['us', 'en', 'ar']) # Load common fallbacks
            vk_instance.current_language = 'us' # Fallback language

    except (XKBManagerError, Exception) as e:
        print(f"XKBManager Initialization FAILED: {e}", file=sys.stderr)
        vk_instance.xkb_manager = None # Ensure it's None on failure
        print("Loading default layouts due to XKB Manager error.")
        load_layout_files_from_system_config(vk_instance, ['us', 'en', 'ar'])
        vk_instance.current_language = 'us'


def load_layout_files_from_system_config(vk_instance, required_layout_codes: List[str]):
    """Loads required .json layout files from the layouts directory."""
    print(f"Loading required layouts ({required_layout_codes}) from: {vk_instance.layouts_dir}")
    if not os.path.isdir(vk_instance.layouts_dir):
        print(f"Warning: Layouts directory not found: {vk_instance.layouts_dir}")
        return

    vk_instance.loaded_layouts = {} # Clear previous layouts

    fallback_codes_to_try = ['us', 'en']
    loaded_fallback_code = None
    for code in fallback_codes_to_try:
        filepath = os.path.join(vk_instance.layouts_dir, f"{code}.json")
        if os.path.exists(filepath):
            if load_single_layout_file_into_instance(vk_instance, code, filepath):
                loaded_fallback_code = code
                break 

    if not loaded_fallback_code and not FALLBACK_CHAR_MAP: 
        print("ERROR: No fallback layout (us.json/en.json) found and FALLBACK_CHAR_MAP is empty!", file=sys.stderr)

    for layout_code in required_layout_codes:
        if layout_code in vk_instance.loaded_layouts: 
            continue
        filepath = os.path.join(vk_instance.layouts_dir, f"{layout_code}.json")
        if os.path.exists(filepath):
            load_single_layout_file_into_instance(vk_instance, layout_code, filepath)
        else:
            print(f"  - Warning: Layout file '{layout_code}.json' not found for system layout '{layout_code}'. Display will use fallback map.")


def load_single_layout_file_into_instance(vk_instance, layout_code: str, filepath: str) -> bool:
    """Loads and validates a single JSON layout file, storing it in vk_instance.loaded_layouts."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            layout_data = json.load(f)
            if isinstance(layout_data, dict):
                valid_structure = True
                for k, v_list in layout_data.items():
                    if not isinstance(k, str) or \
                       not isinstance(v_list, (list, tuple)) or \
                       not (1 <= len(v_list) <= 2) or \
                       not isinstance(v_list[0], str) or \
                       (len(v_list) == 2 and not isinstance(v_list[1], (str, type(None)))): 
                        print(f"  - Warning: Invalid data structure for key '{k}' in {os.path.basename(filepath)} (value: {v_list}). Skipping file.", file=sys.stderr)
                        valid_structure = False
                        break
                if valid_structure:
                    vk_instance.loaded_layouts[layout_code] = layout_data
                    return True
            else:
                print(f"  - Warning: Invalid format in {os.path.basename(filepath)} (expected a dictionary). Skipping.", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"  - Error decoding JSON in {os.path.basename(filepath)}: {e}. Skipping.", file=sys.stderr)
    except IOError as e:
        print(f"  - Error reading file {os.path.basename(filepath)}: {e}. Skipping.", file=sys.stderr)
    except Exception as e:
        print(f"  - Unexpected error loading {os.path.basename(filepath)}: {e}. Skipping.", file=sys.stderr)
    return False


def update_key_labels_on_layout_change(vk_instance, specific_key_name: Optional[str] = None):
    """
    Updates key labels based on the current language and modifier states.
    If specific_key_name is provided, only that key's label is updated.
    Otherwise, all key labels are updated.
    """
    if not hasattr(vk_instance, 'buttons') or not vk_instance.buttons:
        return

    symbol_map = {
        "Caps Lock": "⇪ Caps", "Tab": "⇥ Tab", "Enter": "↵ Enter", "Backspace": "⌫ Bksp",
        "Up": "↑", "Down": "↓", "Left": "←", "Right": "→",
        "L Win": "◆", "R Win": "◆", "App": "☰", "Scroll Lock": "Scroll Lk",
        "Pause": "Pause", "PrtSc":"PrtSc", "Insert":"Ins", "Home":"Home",
        "Page Up":"PgUp", "Delete":"Del", "End":"End", "Page Down":"PgDn",
        "L Ctrl":"Ctrl", "R Ctrl":"Ctrl", "L Alt":"Alt", "R Alt":"AltGr",
        "Space":"Space", "Esc":"Esc", "About":"About", "Set":"Set",
        "LShift": "⇧ Shift", "RShift": "⇧ Shift",
        "Minimize":"_", "Close":"X", "Donate":"Donate"
    }

    active_layout_code = vk_instance.current_language
    active_layout_map = vk_instance.loaded_layouts.get(active_layout_code)
    fallback_map_to_use = vk_instance.loaded_layouts.get('us',
                                vk_instance.loaded_layouts.get('en',
                                    FALLBACK_CHAR_MAP if isinstance(FALLBACK_CHAR_MAP, dict) else {}
                                ))
    if active_layout_map is None: 
        active_layout_map = fallback_map_to_use

    available_layouts = vk_instance.xkb_manager.get_available_layouts() if vk_instance.xkb_manager else list(vk_instance.loaded_layouts.keys())
    if not available_layouts: available_layouts = ['us'] 
    num_layouts = len(available_layouts)
    current_index = -1
    try:
        current_index = available_layouts.index(vk_instance.current_language)
    except ValueError: 
        if vk_instance.current_language in vk_instance.loaded_layouts: 
            current_index = 0 
            available_layouts = [vk_instance.current_language] + [l for l in available_layouts if l != vk_instance.current_language]
            num_layouts = len(available_layouts)
        else: 
            current_index = 0
            available_layouts = ['us']
            num_layouts = 1

    keys_to_process = vk_instance.buttons.items()
    if specific_key_name and specific_key_name in vk_instance.buttons:
        keys_to_process = [(specific_key_name, vk_instance.buttons[specific_key_name])]

    for key_name, button in keys_to_process: 
        if not button: continue 

        new_label = key_name 
        toggled = False 
        is_modifier_visual_key = key_name in ['LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock']

        if key_name.startswith('Lang'):
            target_layout_to_display = "---" 
            display_idx_offset = 0

            if key_name == 'Lang2': 
                display_idx_offset = 0 
            elif key_name == 'Lang1' or key_name == 'Lang3': 
                display_idx_offset = 1
            
            if num_layouts > 0 and current_index != -1:
                if (display_idx_offset == 0) or \
                   (display_idx_offset == 1 and num_layouts > 1):
                    actual_display_index = (current_index + display_idx_offset) % num_layouts
                    target_layout_to_display = available_layouts[actual_display_index]
            
            new_label = target_layout_to_display.upper()
            if len(new_label) > 3 and new_label != "---": new_label = new_label[:2]

        elif key_name in symbol_map:
            new_label = symbol_map[key_name]

        char_tuple = active_layout_map.get(key_name, fallback_map_to_use.get(key_name))

        if char_tuple and isinstance(char_tuple, (list, tuple)) and len(char_tuple) >= 1:
            index_to_use = 0 
            is_letter = key_name.isalpha() and len(key_name) == 1
            should_display_shifted = (vk_instance.shift_pressed ^ vk_instance.caps_lock_pressed) if is_letter else vk_instance.shift_pressed

            if should_display_shifted and len(char_tuple) > 1 and char_tuple[1] is not None: 
                index_to_use = 1

            current_char_to_display = char_tuple[index_to_use] if index_to_use < len(char_tuple) else char_tuple[0]
            if current_char_to_display is not None: 
                 new_label = current_char_to_display
        elif key_name.startswith("F") and key_name[1:].isdigit(): 
            new_label = key_name

        if key_name in ['LShift', 'RShift']: toggled = vk_instance.shift_pressed
        elif key_name in ['L Ctrl', 'R Ctrl']: toggled = vk_instance.ctrl_pressed
        elif key_name in ['L Alt', 'R Alt']: toggled = vk_instance.alt_pressed
        elif key_name == 'Caps Lock': toggled = vk_instance.caps_lock_pressed

        if button.text() != new_label:
            button.setText(new_label)

        if is_modifier_visual_key:
            current_prop = button.property("modifier_on")
            if current_prop is None or current_prop != toggled: 
                button.setProperty("modifier_on", toggled)
                button.style().unpolish(button)
                button.style().polish(button)
        else: 
            current_prop = button.property("modifier_on")
            if current_prop is not None and current_prop is True:
                button.setProperty("modifier_on", False)
                button.style().unpolish(button)
                button.style().polish(button)


def update_single_key_label(vk_instance, key_name: str):
    """Updates the label and state of a single key button."""
    if key_name in vk_instance.buttons:
        update_key_labels_on_layout_change(vk_instance, specific_key_name=key_name)
    else:
        print(f"Warning (update_single_key_label): Key '{key_name}' not found in buttons.")