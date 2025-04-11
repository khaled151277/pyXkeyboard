# -*- coding: utf-8 -*-
# Handles Xlib import, dummy creation, and provides XTEST functions

import sys
# --- ADDED: Import Optional ---
from typing import Optional
# --- END ADDED ---

# Keep the import statement for type hinting if possible, even if using dummy
try:
    import Xlib
    import Xlib.display
    import Xlib.XK
    import Xlib.ext.xtest
    import Xlib.X
except ImportError:
    # Define Xlib as None initially if import fails
    Xlib = None

# Module-level state variables
_is_xlib_dummy = False # Flag indicating if the dummy Xlib is used
_display = None        # Xlib display connection object
_xlib_ok = False       # Flag indicating successful Xlib/XTEST initialization
_shift_keycode = None  # Keycode for Shift_L
_ctrl_keycode = None   # Keycode for Control_L
_alt_keycode = None    # Keycode for Alt_L
_caps_lock_keycode = None # Keycode for Caps_Lock

# --- Xlib Dummy Class (Used if python-xlib is not installed) ---
class Xlib_Dummy:
    """ Dummy class mimicking Xlib structure for basic functionality without the library. """
    class XK: # Mimics Xlib.XK for KeySym constants
        XK_Shift_L, XK_Control_L, XK_Alt_L, XK_Caps_Lock = 1, 2, 3, 4
        XK_Escape, XK_Tab, XK_Return, XK_BackSpace = 5, 6, 7, 8
        XK_Shift_R, XK_Control_R, XK_Alt_R, XK_Super_L, XK_Menu = 9, 10, 11, 12, 13
        XK_space, XK_Print, XK_Scroll_Lock, XK_Pause = 14, 15, 16, 17
        XK_Insert, XK_Home, XK_Page_Up, XK_Delete, XK_End, XK_Page_Down = 18, 19, 20, 21, 22, 23
        XK_Up, XK_Left, XK_Down, XK_Right = 24, 25, 26, 27
        XK_F1, XK_F2, XK_F3, XK_F4, XK_F5, XK_F6 = 28, 29, 30, 31, 32, 33
        XK_F7, XK_F8, XK_F9, XK_F10, XK_F11, XK_F12 = 34, 35, 36, 37, 38, 39
        XK_grave, XK_minus, XK_equal, XK_bracketleft = 40, 41, 42, 43
        XK_bracketright, XK_backslash, XK_semicolon, XK_apostrophe = 44, 45, 46, 47
        XK_comma, XK_period, XK_slash = 48, 49, 50
        XK_1, XK_2, XK_3, XK_4, XK_5, XK_6, XK_7, XK_8, XK_9, XK_0 = 51, 52, 53, 54, 55, 56, 57, 58, 59, 60
        XK_a, XK_b, XK_c, XK_d, XK_e, XK_f, XK_g, XK_h, XK_i, XK_j = 61, 62, 63, 64, 65, 66, 67, 68, 69, 70
        XK_k, XK_l, XK_m, XK_n, XK_o, XK_p, XK_q, XK_r, XK_s, XK_t = 71, 72, 73, 74, 75, 76, 77, 78, 79, 80
        XK_u, XK_v, XK_w, XK_x, XK_y, XK_z = 81, 82, 83, 84, 85, 86

    class display: # Mimics Xlib.display
        _instance = None
        @staticmethod
        def Display(): # Singleton pattern for dummy display
             if Xlib_Dummy.display._instance is None: Xlib_Dummy.display._instance = Xlib_Dummy.display()
             return Xlib_Dummy.display._instance
        def keysym_to_keycode(self, keysym):
            if keysym == Xlib_Dummy.XK.XK_Caps_Lock: return 66
            return 9
        def sync(self): pass
        def close(self): pass
        def flush(self): pass

    class ext: # Mimics Xlib.ext
        class xtest: # Mimics Xlib.ext.xtest
            @staticmethod
            def fake_input(dpy, event_type, keycode): pass

    class X: # Mimics Xlib.X for constants
        KeyPress, KeyRelease = 1, 2

# --- Check if Real Xlib was Imported ---
if Xlib is None:
    # If import failed, use the dummy class
    print("WARNING: python-xlib library not found.")
    print("Install it for key press simulation: pip install python-xlib")
    print("XTEST input simulation will be disabled.")
    Xlib = Xlib_Dummy # Assign the dummy class to the Xlib name
    _is_xlib_dummy = True # Set the flag

# --- Provide Access to Constants (either real or dummy) ---
XK = Xlib.XK
X = Xlib.X

# --- Module-Level Functions ---

def is_dummy():
    """ Returns True if the dummy Xlib implementation is being used. """
    return _is_xlib_dummy

def is_xtest_ok():
    """ Returns True if Xlib initialized correctly and XTEST is expected to work. """
    return _xlib_ok

def get_display():
    """ Returns the active Xlib display object, or None. """
    return _display

def get_shift_keycode() -> Optional[int]:
    """ Returns the keycode for Left Shift, or None. """
    return _shift_keycode

def get_ctrl_keycode() -> Optional[int]:
    """ Returns the keycode for Left Control, or None. """
    return _ctrl_keycode

def get_alt_keycode() -> Optional[int]:
    """ Returns the keycode for Left Alt, or None. """
    return _alt_keycode

def get_caps_lock_keycode() -> Optional[int]:
    """ Returns the keycode for Caps Lock, or None. """
    return _caps_lock_keycode

def initialize_xlib():
    """
    Initializes the connection to the X display and attempts to get necessary
    keycodes for XTEST. Updates module-level state variables.
    Returns True on success, False on failure.
    """
    global _display, _xlib_ok, _shift_keycode, _ctrl_keycode, _alt_keycode, _caps_lock_keycode

    if _is_xlib_dummy:
        print("Xlib Initialized (Integration): Using Dummy (XTEST Disabled)")
        _xlib_ok = False
        return False

    try:
        _display = Xlib.display.Display()
        if _display:
            _shift_keycode = _display.keysym_to_keycode(Xlib.XK.XK_Shift_L)
            _ctrl_keycode = _display.keysym_to_keycode(Xlib.XK.XK_Control_L)
            _alt_keycode = _display.keysym_to_keycode(Xlib.XK.XK_Alt_L)
            _caps_lock_keycode = _display.keysym_to_keycode(Xlib.XK.XK_Caps_Lock)

            if _shift_keycode and _ctrl_keycode and _alt_keycode and _caps_lock_keycode:
                _xlib_ok = True
                print("Xlib Initialized (Integration): SUCCESS (XTEST Enabled)")
                return True
            else:
                missing = [k for k, v in {'Shift': _shift_keycode, 'Ctrl': _ctrl_keycode, 'Alt': _alt_keycode, 'CapsLock': _caps_lock_keycode}.items() if not v]
                print(f"Xlib Initialized (Integration): WARNING - Missing keycodes ({', '.join(missing)}) (XTEST partially/fully Disabled)", file=sys.stderr)
                if _display:
                    try: _display.close()
                    except Exception: pass
                _display = None
                _xlib_ok = False
                return False
        else:
            print("Xlib Initialized (Integration): ERROR - Could not connect to display (XTEST Disabled)", file=sys.stderr)
            _xlib_ok = False
            return False
    except Exception as e:
        print(f"Xlib Initialized (Integration): ERROR - Exception during init: {e} (XTEST Disabled)", file=sys.stderr)
        if _display:
            try: _display.close()
            except Exception: pass
        _display = None
        _xlib_ok = False
        return False

def close_xlib():
    """ Closes the Xlib display connection if it's open. """
    global _display, _xlib_ok
    if _display and not _is_xlib_dummy:
        try:
            print("Closing Xlib display connection...")
            _display.close()
        except Exception as e:
            print(f"ERROR closing X display: {e}", file=sys.stderr)
    _display = None
    _xlib_ok = False

def send_xtest_event(event_type, keycode):
    """ Sends a single XTEST fake input event (KeyPress or KeyRelease).
        Returns True on success, False on failure.
    """
    if _xlib_ok and _display:
        try:
            Xlib.ext.xtest.fake_input(_display, event_type, keycode)
            if not _is_xlib_dummy:
                _display.sync() # Ensure event is processed
            return True
        except Exception as e:
            print(f"ERROR sending XTEST event (Type: {event_type}, KC: {keycode}): {e}", file=sys.stderr)
            return False
    return False

def keysym_to_keycode(keysym) -> Optional[int]: # Added type hint back
    """ Converts an X11 KeySym to a KeyCode using the current display mapping.
        Returns the keycode (int) or None if not found or on error.
    """
    if _xlib_ok and _display:
        try:
            keycode = _display.keysym_to_keycode(keysym)
            # keysym_to_keycode returns 0 if not found, treat 0 as None (not found)
            return keycode if keycode != 0 else None
        except Exception as e:
            print(f"ERROR getting keycode for keysym {hex(keysym)}: {e}", file=sys.stderr)
            return None
    return None

def flush_display():
    """ Flushes the X display connection buffer. """
    if _display and not _is_xlib_dummy:
        try:
            _display.flush()
        except Exception as e:
            print(f"WARNING: Error flushing display: {e}", file=sys.stderr)
