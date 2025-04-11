# -*- coding: utf-8 -*-
# Defines keyboard layout, character mappings, and X11 keysym constants.

# Import XK constants directly from the integration module
# This ensures we use either the real Xlib constants or the dummy ones.
from xlib_integration import XK

# --- KeySym / Character / Layout Definitions ---

# Map button names used in the layout structure (KEYBOARD_LAYOUT) to X11 KeySyms.
# These KeySyms are used by xlib_integration to find KeyCodes for XTEST simulation.
X11_KEYSYM_MAP = {
    'Esc': XK.XK_Escape, 'Tab': XK.XK_Tab, 'Caps Lock': XK.XK_Caps_Lock,
    'LShift': XK.XK_Shift_L, 'RShift': XK.XK_Shift_R,
    'L Ctrl': XK.XK_Control_L, 'R Ctrl': XK.XK_Control_R,
    'L Win': XK.XK_Super_L, 'R Win': 0xce, # Often XK_Super_R, might vary (0xce is common)
    'L Alt': XK.XK_Alt_L, 'R Alt': XK.XK_Alt_R, # Often XK_ISO_Level3_Shift or XK_Mode_switch on some layouts
    'App': XK.XK_Menu, 'Enter': XK.XK_Return, 'Backspace': XK.XK_BackSpace,
    'Space': XK.XK_space, 'PrtSc': XK.XK_Print, 'Scroll Lock': XK.XK_Scroll_Lock,
    'Pause': XK.XK_Pause, 'Insert': XK.XK_Insert, 'Home': XK.XK_Home,
    'Page Up': XK.XK_Page_Up, 'Delete': XK.XK_Delete, 'End': XK.XK_End,
    'Page Down': XK.XK_Page_Down, 'Up': XK.XK_Up, 'Left': XK.XK_Left,
    'Down': XK.XK_Down, 'Right': XK.XK_Right,
    'F1': XK.XK_F1, 'F2': XK.XK_F2, 'F3': XK.XK_F3, 'F4': XK.XK_F4,
    'F5': XK.XK_F5, 'F6': XK.XK_F6, 'F7': XK.XK_F7, 'F8': XK.XK_F8,
    'F9': XK.XK_F9, 'F10': XK.XK_F10, 'F11': XK.XK_F11, 'F12': XK.XK_F12,
    '`': XK.XK_grave, '-': XK.XK_minus, '=': XK.XK_equal,
    '[': XK.XK_bracketleft, ']': XK.XK_bracketright, '\\': XK.XK_backslash,
    ';': XK.XK_semicolon, "'": XK.XK_apostrophe, ',': XK.XK_comma,
    '.': XK.XK_period, '/': XK.XK_slash, '1': XK.XK_1, '2': XK.XK_2,
    '3': XK.XK_3, '4': XK.XK_4, '5': XK.XK_5, '6': XK.XK_6,
    '7': XK.XK_7, '8': XK.XK_8, '9': XK.XK_9, '0': XK.XK_0,
    # Use lowercase keysyms for letters as standard
    'A': XK.XK_a, 'B': XK.XK_b, 'C': XK.XK_c, 'D': XK.XK_d,
    'E': XK.XK_e, 'F': XK.XK_f, 'G': XK.XK_g, 'H': XK.XK_h,
    'I': XK.XK_i, 'J': XK.XK_j, 'K': XK.XK_k, 'L': XK.XK_l,
    'M': XK.XK_m, 'N': XK.XK_n, 'O': XK.XK_o, 'P': XK.XK_p,
    'Q': XK.XK_q, 'R': XK.XK_r, 'S': XK.XK_s, 'T': XK.XK_t,
    'U': XK.XK_u, 'V': XK.XK_v, 'W': XK.XK_w, 'X': XK.XK_x,
    'Y': XK.XK_y, 'Z': XK.XK_z,
    # Special buttons internal to the application, not needing X11 keysyms
    'About': None, 'Lang': None, 'Set': None,
}

# Map internal key names (used in KEYBOARD_LAYOUT) to characters for different layouts.
# Each entry maps a key name to a dictionary of languages.
# Each language maps to a tuple: (normal_char, shifted_char).
KEY_CHAR_MAP = {
    # Row 1 (Numbers)
    '`': {'en': ('`', '~'), 'ar': ('ذ', 'ّ')}, # Added explicit Shadda for Ar+Shift+`
    '1': {'en': ('1', '!'), 'ar': ('١', '!')},
    '2': {'en': ('2', '@'), 'ar': ('٢', '@')},
    '3': {'en': ('3', '#'), 'ar': ('٣', '#')},
    '4': {'en': ('4', '$'), 'ar': ('٤', '$')},
    '5': {'en': ('5', '%'), 'ar': ('٥', '%')},
    '6': {'en': ('6', '^'), 'ar': ('٦', '^')},
    '7': {'en': ('7', '&'), 'ar': ('٧', '&')},
    '8': {'en': ('8', '*'), 'ar': ('٨', '*')},
    '9': {'en': ('9', '('), 'ar': ('٩', '(')},
    '0': {'en': ('0', ')'), 'ar': ('٠', ')')},
    '-': {'en': ('-', '_'), 'ar': ('-', '_')},
    '=': {'en': ('=', '+'), 'ar': ('=', '+')},
    # Row 2 (QWERTY)
    'Q': {'en': ('q', 'Q'), 'ar': ('ض', 'َ')}, # Fatha
    'W': {'en': ('w', 'W'), 'ar': ('ص', 'ً')}, # Tanween Fath
    'E': {'en': ('e', 'E'), 'ar': ('ث', 'ُ')}, # Damma
    'R': {'en': ('r', 'R'), 'ar': ('ق', 'ٌ')}, # Tanween Damm
    'T': {'en': ('t', 'T'), 'ar': ('ف', 'ﻹ')}, # Lam+Alef with Hamza below
    'Y': {'en': ('y', 'Y'), 'ar': ('غ', 'إ')}, # Alef with Hamza below
    'U': {'en': ('u', 'U'), 'ar': ('ع', '‘')}, # Single quote (apostrophe)
    'I': {'en': ('i', 'I'), 'ar': ('ه', '÷')}, # Division sign
    'O': {'en': ('o', 'O'), 'ar': ('خ', '×')}, # Multiplication sign
    'P': {'en': ('p', 'P'), 'ar': ('ح', '؛')}, # Arabic semicolon
    '[': {'en': ('[', '{'), 'ar': ('ج', '<')},
    ']': {'en': (']', '}'), 'ar': ('د', '>')},
    '\\':{'en': ('\\', '|'),'ar': ('\\', '|')}, # Backslash mapping might vary
    # Row 3 (ASDF)
    'A': {'en': ('a', 'A'), 'ar': ('ش', 'ِ')}, # Kasra
    'S': {'en': ('s', 'S'), 'ar': ('س', 'ٍ')}, # Tanween Kasr
    'D': {'en': ('d', 'D'), 'ar': ('ي', ']')}, # Closing square bracket
    'F': {'en': ('f', 'F'), 'ar': ('ب', '[')}, # Opening square bracket
    'G': {'en': ('g', 'G'), 'ar': ('ل', 'ﻷ')}, # Lam+Alef with Hamza above
    'H': {'en': ('h', 'H'), 'ar': ('ا', 'أ')}, # Alef with Hamza above
    'J': {'en': ('j', 'J'), 'ar': ('ت', 'ـ')}, # Tatweel (kashida)
    'K': {'en': ('k', 'K'), 'ar': ('ن', '،')}, # Arabic comma
    'L': {'en': ('l', 'L'), 'ar': ('م', '/')}, # Forward slash
    ';': {'en': (';', ':'), 'ar': ('ك', ':')}, # Colon
    "'": {'en': ("'", '"'), 'ar': ('ط', '"')}, # Double quote
    # Row 4 (ZXCV)
    'Z': {'en': ('z', 'Z'), 'ar': ('ئ', '~')}, # Tilde
    'X': {'en': ('x', 'X'), 'ar': ('ء', 'ْ')}, # Sukun
    'C': {'en': ('c', 'C'), 'ar': ('ؤ', '}')}, # Closing curly brace
    'V': {'en': ('v', 'V'), 'ar': ('ر', '{')}, # Opening curly brace
    'B': {'en': ('b', 'B'), 'ar': ('لا', 'ﻵ')}, # Lam+Alef with Madda above
    'N': {'en': ('n', 'N'), 'ar': ('ى', 'آ')}, # Alef with Madda above
    'M': {'en': ('m', 'M'), 'ar': ('ة', '’')}, # Single closing quote/apostrophe
    ',': {'en': (',', '<'), 'ar': ('و', ',')}, # Comma
    '.': {'en': ('.', '>'), 'ar': ('ز', '.')}, # Period
    '/': {'en': ('/', '?'), 'ar': ('ظ', '؟')}, # Arabic question mark
}

# Defines the visual layout of the keyboard.
# List of rows, where each row is a list of key definitions or None.
# Key definition format: (key_name_str, row_span_int, col_span_int)
# key_name_str must match keys in X11_KEYSYM_MAP or KEY_CHAR_MAP or be special ('Lang', 'Set', 'About').
# None represents an empty space in the grid layout.
KEYBOARD_LAYOUT = [
    # Function keys row
    [('Esc', 1, 1), ('F1', 1, 1), ('F2', 1, 1), ('F3', 1, 1), ('F4', 1, 1), None, ('F5', 1, 1), ('F6', 1, 1), ('F7', 1, 1), ('F8', 1, 1), None, ('F9', 1, 1), ('F10', 1, 1), ('F11', 1, 1), ('F12', 1, 1), None, ('PrtSc', 1, 1), ('Scroll Lock', 1, 1), ('Pause', 1, 1), ('Lang', 1, 1)],
    # Number row
    [('`', 1, 1), ('1', 1, 1), ('2', 1, 1), ('3', 1, 1), ('4', 1, 1), ('5', 1, 1), ('6', 1, 1), ('7', 1, 1), ('8', 1, 1), ('9', 1, 1), ('0', 1, 1), ('-', 1, 1), ('=', 1, 1), ('Backspace', 1, 2), None, ('Insert', 1, 1), ('Home', 1, 1), ('Page Up', 1, 1), ('About', 1, 1)],
    # QWERTY row
    [('Tab', 1, 2), ('Q', 1, 1), ('W', 1, 1), ('E', 1, 1), ('R', 1, 1), ('T', 1, 1), ('Y', 1, 1), ('U', 1, 1), ('I', 1, 1), ('O', 1, 1), ('P', 1, 1), ('[', 1, 1), (']', 1, 1), ('\\', 1, 1), None, ('Delete', 1, 1), ('End', 1, 1), ('Page Down', 1, 1), ('Set', 1, 1)],
    # ASDF row (Home row)
    [('Caps Lock', 1, 2), ('A', 1, 1), ('S', 1, 1), ('D', 1, 1), ('F', 1, 1), ('G', 1, 1), ('H', 1, 1), ('J', 1, 1), ('K', 1, 1), ('L', 1, 1), (';', 1, 1), ("'", 1, 1), ('Enter', 1, 2), None, None, None, None ], # Added Nones for spacing
    # ZXCV row
    [('LShift', 1, 3), ('Z', 1, 1), ('X', 1, 1), ('C', 1, 1), ('V', 1, 1), ('B', 1, 1), ('N', 1, 1), ('M', 1, 1), (',', 1, 1), ('.', 1, 1), ('/', 1, 1), ('RShift', 1, 3), None, None, ('Up', 1, 1), None ], # Added Nones for spacing
    # Bottom row (Modifiers, Space, etc.)
    [('L Ctrl', 1, 2), ('L Win', 1, 1), ('L Alt', 1, 1), ('Space', 1, 7), ('R Alt', 1, 1), ('R Win', 1, 1), ('App', 1, 1), ('R Ctrl', 1, 2), None, ('Left', 1, 1), ('Down', 1, 1), ('Right', 1, 1)]
]
