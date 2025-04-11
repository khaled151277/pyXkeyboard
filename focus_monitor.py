#!/usr/bin/env python
# -*- coding: utf-8 -*-

# File: focus_monitor.py
# Monitors AT-SPI focus events to detect when focus enters an editable text field.

import sys
import gi
import threading
import time # For example usage

# Ensure gi and atspi requirements are met
try:
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, GObject, GLib
except (ImportError, ValueError) as e:
    print(f"ERROR: gi or Atspi requirements not met in focus_monitor module.")
    print(f"Ensure python3-gi and gir1.2-atspi-2.0 (or equivalent for your distribution) are installed.")
    print(f"Original error: {e}")
    # Don't exit here; let the importer handle it or raise a custom exception if desired.
    raise ImportError("Failed to import Atspi requirements") from e

# List of roles considered as writable text fields
# Make it a class attribute or module constant
EDITABLE_TEXT_ROLES = [
    Atspi.Role.TEXT,
    Atspi.Role.PASSWORD_TEXT,
    # Atspi.Role.TEXT_AREA, # Still pending investigation if needed/reliable
    Atspi.Role.PARAGRAPH, # E.g., contentEditable divs
    Atspi.Role.DOCUMENT_FRAME, # E.g., some rich text editors
    Atspi.Role.EMBEDDED, # Sometimes used for text fields within other components
]

class EditableFocusMonitor:
    """
    Monitors AT-SPI focus events and detects when focus moves
    to an editable text field.
    """
    def __init__(self, user_callback):
        """
        Initialize the monitor.
        :param user_callback: Function to call when an editable text field is detected.
                              This function will receive the Atspi.Accessible object as an argument.
        """
        if not callable(user_callback):
            raise ValueError("user_callback must be a callable function.")

        self._user_callback = user_callback
        self._listener = None # AT-SPI event listener object
        self._loop = None # GLib MainLoop for the listener thread
        self._thread = None # Thread running the GLib MainLoop
        self._running = False # Flag indicating if the monitor is active

    def _internal_on_focus_change(self, event):
        """ Internal callback to process AT-SPI events. """
        try:
            # Get the accessible object that sourced the event
            accessible = event.source
            if not accessible:
                return

            # Check object validity before using it (to avoid some random errors)
            try:
                 _ = accessible.get_name() # Attempting any method call can trigger error if invalid
            except GLib.Error as ge:
                 if "invalid object" in str(ge).lower():
                     return # Ignore invalid objects
                 else:
                      raise # Re-raise other GLib errors
            except AttributeError:
                 return # Ignore if object lacks methods immediately after focus change

            # Get the role and state set of the focused object
            role = accessible.get_role()
            states = accessible.get_state_set()

            # Check if the object is editable and currently focused
            is_editable = states.contains(Atspi.StateType.EDITABLE)
            is_focused = states.contains(Atspi.StateType.FOCUSED) # Ensure it actually gained focus

            # Check if the role is one we consider editable text
            if role in EDITABLE_TEXT_ROLES and is_editable and is_focused:
                # Call the user-provided callback function
                try:
                    self._user_callback(accessible)
                except Exception as cb_e:
                    # Catch errors specifically within the user's callback
                    print(f"ERROR inside user callback: {cb_e}", file=sys.stderr)

        except Exception as e:
            # Avoid printing common, often harmless errors during focus changes
            err_str = str(e).lower()
            if "invalid object" not in err_str and \
               "'nonetype' object has no attribute" not in err_str and \
               "unknown error" not in err_str:
                 print(f"ERROR in internal focus handler: {e}", file=sys.stderr)

    def start(self):
        """ Start the monitoring process in a background thread. """
        if self._running:
            print("Monitor is already running.")
            return

        print("Starting AT-SPI focus event monitor...")
        try:
            # Create a new event listener that calls our internal handler
            self._listener = Atspi.EventListener.new(self._internal_on_focus_change)
            # Register for the specific event: focus changes
            ok = self._listener.register("object:state-changed:focused")
            if not ok:
                 print("WARNING: Failed to register 'object:state-changed:focused' listener (returned false).", file=sys.stderr)

            print("Event listener registered successfully.")
        except Exception as e:
            print(f"Failed to register event listener: {e}", file=sys.stderr)
            print("Is the at-spi bus service running? (e.g., 'at-spi-bus-launcher')")
            self._listener = None
            return # Cannot start without a listener

        # Setup and start the GLib main loop in a separate thread
        self._loop = GLib.MainLoop()
        self._thread = threading.Thread(target=self._loop.run, daemon=True) # Daemon allows exit
        self._running = True
        self._thread.start()
        print("Monitor started and running in the background.")

    def stop(self):
        """ Stop the monitoring process and clean up resources. """
        if not self._running:
            # print("Monitor is not running.") # Less verbose
            return

        print("Stopping monitor...")
        # Quit the GLib main loop
        if self._loop and self._loop.is_running():
            self._loop.quit()

        # Wait for the background thread to exit
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0) # Wait up to 1 second
            if self._thread.is_alive():
                 print("WARNING: Monitor thread did not terminate cleanly.", file=sys.stderr)

        # Deregister the event listener
        if self._listener:
            try:
                self._listener.deregister("object:state-changed:focused")
                print("Listener deregistered.")
            except Exception as e:
                print(f"ERROR during listener deregistration: {e}", file=sys.stderr)

        # Clear references
        self._listener = None
        self._loop = None
        self._thread = None
        self._running = False
        print("Monitor stopped.")

    def is_running(self):
        """ Check if the monitor is currently running. """
        # Check both the flag and if the thread is alive
        return self._running and self._thread and self._thread.is_alive()

# --- Example Usage (only runs when script is executed directly) ---
if __name__ == "__main__":

    def my_example_callback(accessible_object):
        """ Example callback function, prints object role and name. """
        try:
            # Use Atspi helper to get human-readable role name
            role_name = Atspi.Role.get_name(accessible_object.get_role())
            name = accessible_object.get_name()
            print(f"  [Callback] Focused on: Role='{role_name}', Name='{name}'")
        except Exception as e:
            print(f"  [Callback] ERROR: {e}")

    # Create the monitor instance, passing the example callback
    monitor = EditableFocusMonitor(user_callback=my_example_callback)

    try:
        # Start the monitor
        monitor.start()

        # Keep the main script alive to listen for events
        if monitor.is_running():
             print("\nMonitor is running. Press Ctrl+C to stop.")
             while monitor.is_running():
                 time.sleep(0.5) # Wait briefly, check status
        else:
             print("\nMonitor failed to start.")

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\nStop requested (Ctrl+C)...")
    except ImportError as e:
         # Handle import errors caught during initialization
         print(f"Failed to import requirement: {e}")
    except Exception as e:
         # Catch other unexpected errors in the main example block
         print(f"Unexpected error in main execution: {e}")
    finally:
        # Ensure the monitor is always stopped on exit
        if 'monitor' in locals() and monitor and monitor.is_running():
            monitor.stop()
        print("Main script finished.")
