# -*- coding: utf-8 -*-
# file:settings_manager.py
# PyXKeyboard v1.0.3 - A simple, customizable on-screen virtual keyboard.
# Features include X11 key simulation (XTEST), system layout switching (XKB),
# visual layout updates, configurable appearance (fonts, colors, opacity, styles),
# auto-repeat, system tray integration, and optional AT-SPI based auto-show.
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.
# Handles loading, saving, and default values for application settings.

import os
import json
import sys # For error printing
import copy # For deepcopy

# --- *** تعديل: تغيير اسم المجلد *** ---
# Define the directory and file for storing settings
SETTINGS_DIR = os.path.expanduser("~/.pyxkeyboard") # Changed from .xkyboard
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
# --- *** نهاية التعديل *** ---

# --- *** تعديل: تحديث الإعدادات الافتراضية *** ---
# Default settings values used if the file doesn't exist or is invalid
DEFAULT_SETTINGS = {
    "remember_geometry": True,
    "window_geometry": { # Provided a default geometry
        "x": 370,
        "y": 340,
        "width": 610,
        "height": 140
    },
    "font_family": "Noto Naskh Arabic", # Changed font
    "font_size": 10,                   # Changed font size
    "use_system_colors": True,         # Changed default to True
    "window_background_color": "#353636", # Default custom window bg
    "button_background_color": "#000000", # Default custom button bg (flat)
    "window_opacity": 0.9,             # Changed default opacity
    "text_color": "#ffffff",            # Default custom text color
    "auto_hide_on_middle_click": True,
    "auto_show_on_edit": False,
    "button_style": "default",
    "frameless_window": True,
    "always_on_top": True,
    "sticky_on_all_workspaces": False, # Still not implemented
    "auto_repeat_enabled": True,
    "auto_repeat_delay_ms": 1000,      # Changed repeat delay
    "auto_repeat_interval_ms": 100,
}
# --- *** نهاية التعديل *** ---

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
            # --- Handle potential invalid geometry from old file ---
            if "window_geometry" in loaded_settings and not isinstance(loaded_settings["window_geometry"], dict):
                print("   - Ignoring invalid 'window_geometry' from saved file.")
                del loaded_settings["window_geometry"] # Remove invalid entry before merging
            # --- End Geometry Check ---
            settings.update(loaded_settings) # Update defaults with loaded values

            # Check if any keys were missing from the file and added from defaults
            if len(settings) > len(loaded_settings):
                 print("-> Added missing default keys to loaded settings.")

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
        settings_to_save = copy.deepcopy(DEFAULT_SETTINGS)
        # --- Handle potential invalid geometry before saving ---
        if "window_geometry" in settings_dict and not isinstance(settings_dict["window_geometry"], dict):
             print("   - Removing invalid 'window_geometry' before saving.")
             settings_dict.pop("window_geometry", None) # Remove if invalid
        # --- End Geometry Check ---
        settings_to_save.update(settings_dict)

        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
        print(f"-> Settings save successful.")

    except IOError as e:
        print(f"-> ERROR saving settings to {SETTINGS_FILE}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"-> UNEXPECTED ERROR saving settings: {e}", file=sys.stderr)
# file:settings_manager.py
