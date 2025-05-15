#!/usr/bin/python3
# -*- coding: utf-8 -*-

# file: pyxkeyboard.py (to be installed as /usr/bin/pyxkeyboard)
# PyXKeyboard v1.0.7 - Launcher Script
# This script ensures the package is in the Python path and runs the main function.
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

import sys
import os
import site
# import locale # Localization not yet implemented

# --- Localization Setup (Placeholder) ---
# locale.bindtextdomain('pyxkeyboard', '/usr/share/locale') # Example path
# locale.textdomain('pyxkeyboard')
# _ = locale.gettext

# --- Add Standard Installation Paths to Python Path ---
# This is important to ensure the pyxkeyboard module is found after installation.

def add_to_sys_path_if_exists(path_to_add):
    """Adds a directory to sys.path if it exists and isn't already there."""
    if os.path.isdir(path_to_add) and path_to_add not in sys.path:
        # site.addsitedir(path_to_add) # Another way, sometimes preferable
        sys.path.insert(0, path_to_add) # Prepend to prioritize over dev versions
        # print(f"Debug: Added to sys.path: {path_to_add}") # For diagnostics only

# Common system-wide package locations (adjust based on distribution if needed)
common_system_paths = [
    "/usr/lib/python3/dist-packages",    # Debian/Ubuntu
    "/usr/lib64/python3/site-packages",  # Fedora/RHEL 64-bit
    "/usr/lib/python3/site-packages",    # Other Linux, or 32-bit Fedora/RHEL
]

for path in common_system_paths:
    add_to_sys_path_if_exists(path)

# Attempt to add the site-packages path for the current Python version specifically
try:
    py_version_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    
    # Standard system site-packages for this version
    # sys_site_packages_path = f"/usr/lib/python{py_version_major_minor}/site-packages"
    # add_to_sys_path_if_exists(sys_site_packages_path)
    
    # User-local site-packages (less common for system-wide launchers, but for completeness)
    # local_user_site_packages = site.getusersitepackages()
    # add_to_sys_path_if_exists(local_user_site_packages)

    # Debian/Ubuntu specific local path
    local_dist_packages_path = f"/usr/local/lib/python{py_version_major_minor}/dist-packages"
    add_to_sys_path_if_exists(local_dist_packages_path)
    
    # RPM-based specific local path
    local_site_packages_path_rpm = f"/usr/local/lib/python{py_version_major_minor}/site-packages"
    add_to_sys_path_if_exists(local_site_packages_path_rpm)

except Exception as e:
    print(f"Warning: Could not dynamically add specific Python version site-packages path: {e}", file=sys.stderr)


# --- Attempt to run from source tree (for development/testing) ---
# This part might be less relevant for an installed launcher, but harmless.
# It assumes the launcher might be in a bin dir relative to the package.
# For a system-installed launcher, the package should already be in a known site-packages.
try:
    # If this script is /usr/bin/pyxkeyboard, this won't find the source typically.
    # The sys.path additions above are more critical for installed versions.
    # PROJECT_ROOT_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # if PROJECT_ROOT_DIRECTORY not in sys.path:
    #     sys.path.insert(0, PROJECT_ROOT_DIRECTORY)
    #     print(f"Debug: Added project root to sys.path: {PROJECT_ROOT_DIRECTORY}") # Dev only
    pass
except Exception as e:
     print(f"Debug: Error determining project root for dev: {e}", file=sys.stderr)


# --- Import and Run the Main Application Module ---
try:
    # The 'pyxkeyboard' package should now be findable via the modified sys.path
    from pyxkeyboard import main as pyx_main_module # Import the main.py module
    # print("Debug: Successfully imported pyxkeyboard.main module") # Diagnostics
    
    # Call the main function within that module
    pyx_main_module.main()

except ImportError:
    print("FATAL ERROR: Could not import the 'pyxkeyboard' module.", file=sys.stderr)
    print("This usually means the PyXKeyboard package is not installed correctly or not in Python's search path.", file=sys.stderr)
    print("Current Python search paths (sys.path):", file=sys.stderr)
    print("\n".join(sys.path), file=sys.stderr)
    sys.exit(1)
except AttributeError:
    # This would happen if 'main' function is missing in pyxkeyboard.main
    print("FATAL ERROR: Could not find the 'main' function within the 'pyxkeyboard.main' module.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"FATAL ERROR: An unexpected error occurred during application startup: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# file: pyxkeyboard_launcher.py (Conceptual name for the installed script)
