# -*- coding: utf-8 -*-
# Handles loading, saving, and default values for application settings.

import os
import json
import sys # For error printing
import copy # For deepcopy

# Define the directory and file for storing settings
SETTINGS_DIR = os.path.expanduser("~/.xkyboard")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

# Default settings values used if the file doesn't exist or is invalid
DEFAULT_SETTINGS = {
    "remember_geometry": True,
    "window_geometry": None, # Expected format: {"x": int, "y": int, "width": int, "height": int}
    "font_family": "Sans Serif",
    "font_size": 9,
    "window_opacity": 1.0,
    "text_color": "#000000",
    "auto_hide_on_middle_click": True,
    "auto_show_on_edit": False,
    "button_style": "default",
    "frameless_window": False,
    "always_on_top": True,             # تمكين البقاء في المقدمة افتراضيًا
    # --- تمت الإضافة: إعداد الالتصاق بمساحات العمل ---
    "sticky_on_all_workspaces": False, # تعطيل الالتصاق افتراضيًا
    # --- نهاية الإضافة ---
    "auto_repeat_enabled": True,        # تمكين التكرار افتراضيًا
    "auto_repeat_delay_ms": 1500,       # التأخير الأولي قبل بدء التكرار (1.5 ثانية)
    "auto_repeat_interval_ms": 100,     # الفاصل الزمني بين التكرارات (100 ميلي ثانية)
}

def load_settings():
    """ Loads settings from the JSON file.
        Returns the loaded settings dictionary or defaults on error.
    """
    print(f"Attempting to load settings from: {SETTINGS_FILE}")
    if not os.path.exists(SETTINGS_FILE):
        print(f"-> Settings file not found, using defaults.")
        return copy.deepcopy(DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            print(f"-> Opened settings file for reading.")
            loaded_settings = json.load(f)
            print(f"-> Successfully loaded JSON data.")

            # Merge with defaults to ensure all keys exist
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            settings.update(loaded_settings) # Update defaults with loaded values

            # Check if any keys were missing from the file and added from defaults
            if len(settings) > len(loaded_settings):
                 print("-> Added missing default keys to loaded settings.")
                 # Optionally save back immediately to persist new default keys
                 # save_settings(settings)

            print("-> Settings load successful.")
            return settings

    except (json.JSONDecodeError, IOError) as e:
        print(f"-> ERROR loading settings file ({SETTINGS_FILE}): {e}. Using defaults.", file=sys.stderr)
        return copy.deepcopy(DEFAULT_SETTINGS)
    except Exception as e:
        print(f"-> UNEXPECTED ERROR loading settings: {e}. Using defaults.", file=sys.stderr)
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings_dict):
    """ Saves the provided settings dictionary to the JSON file. """
    print(f"Attempting to save settings to: {SETTINGS_FILE}")
    try:
        if not os.path.exists(SETTINGS_DIR):
            os.makedirs(SETTINGS_DIR, exist_ok=True)
            print(f"-> Created settings directory: {SETTINGS_DIR}")

        # Ensure all current default keys exist before saving
        # This is slightly redundant if load_settings merges, but safe
        settings_to_save = copy.deepcopy(DEFAULT_SETTINGS)
        settings_to_save.update(settings_dict)

        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
        print(f"-> Settings save successful.")

    except IOError as e:
        print(f"-> ERROR saving settings to {SETTINGS_FILE}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"-> UNEXPECTED ERROR saving settings: {e}", file=sys.stderr)
