# -*- coding: utf-8 -*-
# Handles loading, saving, and default values for application settings.

import os
import json
import sys # For error printing
import copy # For deepcopy

# Define the directory and file for storing settings
# Uses user's home directory (~/.xkyboard)
SETTINGS_DIR = os.path.expanduser("~/.xkyboard")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

# Default settings values used if the file doesn't exist or is invalid
DEFAULT_SETTINGS = {
    "remember_geometry": True,
    "window_geometry": None, # Expected format: {"x": int, "y": int, "width": int, "height": int}
    "font_family": "Sans Serif", # Default font
    "font_size": 9,             # Default font size
    "window_opacity": 1.0,      # Default opacity (1.0 = fully opaque background)
    "text_color": "#000000",     # Default text color (black for light theme) - Adjust if needed!
    "auto_hide_on_middle_click": True, # Minimize on middle click behaviour
    "auto_show_on_edit": False,   # Auto-show feature default state
    "button_style": "default"     # Button style ("default", "flat", "gradient")
}

def load_settings():
    """ Loads settings from the JSON file.
        Returns the loaded settings dictionary or defaults on error.
    """
    print(f"Attempting to load settings from: {SETTINGS_FILE}")
    if not os.path.exists(SETTINGS_FILE):
        print(f"-> Settings file not found, using defaults.")
        return copy.deepcopy(DEFAULT_SETTINGS) # Return a copy of defaults

    try:
        # Open and read the settings file
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            print(f"-> Opened settings file for reading.")
            settings = json.load(f)
            print(f"-> Successfully loaded JSON data.")

            # --- Ensure all default keys exist, adding missing ones ---
            updated = False
            # Use a separate copy to avoid modifying the global default during iteration
            current_defaults = DEFAULT_SETTINGS
            for key, default_value in current_defaults.items():
                if key not in settings:
                    print(f"   - Adding missing key '{key}' with default value '{default_value}'.")
                    settings[key] = default_value
                    updated = True
            if updated:
                print("-> Added missing default keys to loaded settings.")
            # --- End Key Check ---

            print("-> Settings load successful.")
            return settings # Return the potentially updated settings dictionary

    except (json.JSONDecodeError, IOError) as e:
        # Handle file read or JSON parsing errors
        print(f"-> ERROR loading settings file ({SETTINGS_FILE}): {e}. Using defaults.", file=sys.stderr)
        return copy.deepcopy(DEFAULT_SETTINGS) # Return a copy of defaults
    except Exception as e:
        # Catch any other unexpected errors during loading
        print(f"-> UNEXPECTED ERROR loading settings: {e}. Using defaults.", file=sys.stderr)
        return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings_dict):
    """ Saves the provided settings dictionary to the JSON file. """
    print(f"Attempting to save settings to: {SETTINGS_FILE}")
    try:
        # Ensure the settings directory exists, create if not
        if not os.path.exists(SETTINGS_DIR):
            os.makedirs(SETTINGS_DIR, exist_ok=True) # exist_ok=True prevents error if dir exists
            print(f"-> Created settings directory: {SETTINGS_DIR}")

        # Write the settings dictionary to the file
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            # print(f"-> Opened settings file for writing.") # Less verbose
            # Use indent for readability, ensure_ascii=False for potential non-ASCII chars
            json.dump(settings_dict, f, indent=4, ensure_ascii=False)
            # print(f"-> Successfully wrote JSON data.") # Less verbose
        print(f"-> Settings save successful.")

    except IOError as e:
        # Handle file writing errors (e.g., permissions)
        print(f"-> ERROR saving settings to {SETTINGS_FILE}: {e}", file=sys.stderr)
    except Exception as e:
        # Catch any other unexpected errors during saving
        print(f"-> UNEXPECTED ERROR saving settings: {e}", file=sys.stderr)
