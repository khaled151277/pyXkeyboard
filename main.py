# -*- coding: utf-8 -*-
# Main entry point for the Python XKeyboard application.

import sys
import os
import traceback

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
except ImportError:
    print("FATAL ERROR: PyQt6 library is required to run the application.")
    print("Please install it: pip install PyQt6")
    sys.exit(1)

# Import the main window class AFTER checking PyQt6
try:
    from virtual_keyboard_gui import VirtualKeyboard
    from settings_manager import SETTINGS_DIR # Import for log message
except ImportError as e:
    print(f"FATAL ERROR: Could not import application components: {e}")
    # Attempt to show a message box if QApplication is available
    try:
        # Create a minimal QApplication to show the error message
        err_app = QApplication([])
        QMessageBox.critical(None, "Import Error",
                             f"Failed to import required application modules:\n\n{e}\n\n"
                             "Ensure all .py files (virtual_keyboard_gui.py, settings_dialog.py, etc.) "
                             "are in the same directory or accessible via PYTHONPATH.")
    except Exception as msg_e:
        # If even showing the message box fails, print to stderr
        print(f"Could not display import error message box: {msg_e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    # Catch any other unexpected errors during imports
    print(f"FATAL ERROR: Unexpected error during imports: {e}")
    traceback.print_exc()
    sys.exit(1)


# --- Main Execution Block ---
if __name__ == "__main__":
    print("Starting Python XKeyboard Application...")
    print(f"Using settings directory: {SETTINGS_DIR}")

    # Basic environment check for potential issues
    if os.environ.get("WAYLAND_DISPLAY"):
         print("--- WARNING: Wayland Detected ---")
         print("   XTEST/XKB features might be unreliable or non-functional.")
         print("   Window transparency might also behave differently.")
         print("   Auto-show on edit (AT-SPI) might not work reliably.")
         print("---")
    if not os.environ.get("DISPLAY"):
         print("--- WARNING: DISPLAY environment variable not set. X features may fail. ---")

    # Create the main QApplication instance
    # Note: Must be created *before* any QWidgets (like VirtualKeyboard)
    app = QApplication(sys.argv)
    # Prevent the application from exiting automatically when the main window is closed
    app.setQuitOnLastWindowClosed(False)

    keyboard_window = None
    try:
        # Create and Show the Main Window
        print("Initializing main window...")
        keyboard_window = VirtualKeyboard()
        print("Showing main window...")
        keyboard_window.show()
        print("Main window shown.")

    except Exception as e:
        # Catch-all for fatal errors during initialization or showing the window
        print(f"FATAL ERROR during application initialization: {e}")
        traceback.print_exc()
        # Try to show a critical error message to the user
        QMessageBox.critical(None, "Initialization Error",
                             f"Failed to initialize or show the virtual keyboard:\n\n{e}\n\n"
                             "Check console output for details. Common causes:\n"
                             "- Missing dependencies (PyQt6, python-xlib, python-gi, gir1.2-atspi-2.0).\n"
                             "- Cannot connect to X display (check DISPLAY env var).\n"
                             "- Errors initializing XKB Manager (setxkbmap) or Xlib/XTEST.\n"
                             "- Errors reading/writing settings file (~/.xkyboard/settings.json).\n"
                             "- AT-SPI accessibility services not running or misconfigured.\n"
                             "- Permissions issues.")
        sys.exit(1)

    # Start the Qt Event Loop
    print("Application running. Close window to minimize, use tray menu to quit.")
    exit_code = app.exec()
    print(f"Application finished with exit code {exit_code}.")

    # Exit the script with the application's exit code
    sys.exit(exit_code)
