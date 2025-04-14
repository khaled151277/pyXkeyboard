# -*- coding: utf-8 -*-
# Defines keyboard layout, character mappings, and X11 keysym constants.

from .xlib_integration import XK

# --- KeySym / Character / Layout Definitions ---

X11_KEYSYM_MAP = {
    'Esc': XK.XK_Escape, 'Tab': XK.XK_Tab, 'Caps Lock': XK.XK_Caps_Lock,
    'LShift': XK.XK_Shift_L, 'RShift': XK.XK_Shift_R,
    'L Ctrl': XK.XK_Control_L, 'R Ctrl': XK.XK_Control_R,
    'L Win': XK.XK_Super_L,
    'R Win': 0xfe08, # Changed from 0xce to user-specified 0xfe08 (Often XK_Super_R)
    'L Alt': XK.XK_Alt_L, 'R Alt': XK.XK_Alt_R,
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
    'A': XK.XK_a, 'B': XK.XK_b, 'C': XK.XK_c, 'D': XK.XK_d,
    'E': XK.XK_e, 'F': XK.XK_f, 'G': XK.XK_g, 'H': XK.XK_h,
    'I': XK.XK_i, 'J': XK.XK_j, 'K': XK.XK_k, 'L': XK.XK_l,
    'M': XK.XK_m, 'N': XK.XK_n, 'O': XK.XK_o, 'P': XK.XK_p,
    'Q': XK.XK_q, 'R': XK.XK_r, 'S': XK.XK_s, 'T': XK.XK_t,
    'U': XK.XK_u, 'V': XK.XK_v, 'W': XK.XK_w, 'X': XK.XK_x,
    'Y': XK.XK_y, 'Z': XK.XK_z,
    'About': None, 'Lang': None, 'Set': None,
    'Minimize': None, 'Close': None,
    'Donate': None,
}

KEY_CHAR_MAP = {
    # Row 1 (Numbers)
    '`': {'en': ('`', '~'), 'ar': ('ذ', 'ّ')},
    '1': {'en': ('1', '!'), 'ar': ('١', '!')}, '2': {'en': ('2', '@'), 'ar': ('٢', '@')},
    '3': {'en': ('3', '#'), 'ar': ('٣', '#')}, '4': {'en': ('4', '$'), 'ar': ('٤', '$')},
    '5': {'en': ('5', '%'), 'ar': ('٥', '%')}, '6': {'en': ('6', '^'), 'ar': ('٦', '^')},
    '7': {'en': ('7', '&'), 'ar': ('٧', '&')}, '8': {'en': ('8', '*'), 'ar': ('٨', '*')},
    '9': {'en': ('9', '('), 'ar': ('٩', '(')}, '0': {'en': ('0', ')'), 'ar': ('٠', ')')},
    '-': {'en': ('-', '_'), 'ar': ('-', '_')}, '=': {'en': ('=', '+'), 'ar': ('=', '+')},
    # Row 2 (QWERTY)
    'Q': {'en': ('q', 'Q'), 'ar': ('ض', 'َ')}, 'W': {'en': ('w', 'W'), 'ar': ('ص', 'ً')},
    'E': {'en': ('e', 'E'), 'ar': ('ث', 'ُ')}, 'R': {'en': ('r', 'R'), 'ar': ('ق', 'ٌ')},
    'T': {'en': ('t', 'T'), 'ar': ('ف', 'ﻹ')}, 'Y': {'en': ('y', 'Y'), 'ar': ('غ', 'إ')},
    'U': {'en': ('u', 'U'), 'ar': ('ع', '‘')}, 'I': {'en': ('i', 'I'), 'ar': ('ه', '÷')},
    'O': {'en': ('o', 'O'), 'ar': ('خ', '×')}, 'P': {'en': ('p', 'P'), 'ar': ('ح', '؛')},
    '[': {'en': ('[', '{'), 'ar': ('ج', '<')}, ']': {'en': (']', '}'), 'ar': ('د', '>')},
    '\\':{'en': ('\\', '|'),'ar': ('\\', '|')},
    # Row 3 (ASDF)
    'A': {'en': ('a', 'A'), 'ar': ('ش', 'ِ')}, 'S': {'en': ('s', 'S'), 'ar': ('س', 'ٍ')},
    'D': {'en': ('d', 'D'), 'ar': ('ي', ']')}, 'F': {'en': ('f', 'F'), 'ar': ('ب', '[')},
    'G': {'en': ('g', 'G'), 'ar': ('ل', 'ﻷ')}, 'H': {'en': ('h', 'H'), 'ar': ('ا', 'أ')},
    'J': {'en': ('j', 'J'), 'ar': ('ت', 'ـ')}, 'K': {'en': ('k', 'K'), 'ar': ('ن', '،')},
    'L': {'en': ('l', 'L'), 'ar': ('م', '/')}, ';': {'en': (';', ':'), 'ar': ('ك', ':')},
    "'": {'en': ("'", '"'), 'ar': ('ط', '"')},
    # Row 4 (ZXCV)
    'Z': {'en': ('z', 'Z'), 'ar': ('ئ', '~')}, 'X': {'en': ('x', 'X'), 'ar': ('ء', 'ْ')},
    'C': {'en': ('c', 'C'), 'ar': ('ؤ', '}')}, 'V': {'en': ('v', 'V'), 'ar': ('ر', '{')},
    'B': {'en': ('b', 'B'), 'ar': ('لا', 'ﻵ')}, 'N': {'en': ('n', 'N'), 'ar': ('ى', 'آ')},
    'M': {'en': ('m', 'M'), 'ar': ('ة', '’')}, ',': {'en': (',', '<'), 'ar': ('و', ',')},
    '.': {'en': ('.', '>'), 'ar': ('ز', '.')}, '/': {'en': ('/', '?'), 'ar': ('ظ', '؟')},
}


# --- تم التحديث: تغيير مكان زر التبرع وتعديل الصفوف الأخرى ---
KEYBOARD_LAYOUT = [
    # Row 1: Function keys row (Unchanged)
    [('Esc', 1, 1), ('F1', 1, 1), ('F2', 1, 1), ('F3', 1, 1), ('F4', 1, 1), None, ('F5', 1, 1), ('F6', 1, 1), ('F7', 1, 1), ('F8', 1, 1), None, ('F9', 1, 1), ('F10', 1, 1), ('F11', 1, 1), ('F12', 1, 1), None, ('Minimize', 1, 2), ('Close', 1, 2)],
    # Row 2: Number row (Unchanged)
    [('`', 1, 1), ('1', 1, 1), ('2', 1, 1), ('3', 1, 1), ('4', 1, 1), ('5', 1, 1), ('6', 1, 1), ('7', 1, 1), ('8', 1, 1), ('9', 1, 1), ('0', 1, 1), ('-', 1, 1), ('=', 1, 1), ('Backspace', 1, 2), None, ('PrtSc', 1, 1), ('Scroll Lock', 1, 1), ('Pause', 1, 1), ('Lang', 1, 1)],
    # Row 3: QWERTY row (Donate button removed from here)
    [('Tab', 1, 2), ('Q', 1, 1), ('W', 1, 1), ('E', 1, 1), ('R', 1, 1), ('T', 1, 1), ('Y', 1, 1), ('U', 1, 1), ('I', 1, 1), ('O', 1, 1), ('P', 1, 1), ('[', 1, 1), (']', 1, 1), ('\\', 1, 1), None, ('Insert', 1, 1), ('Home', 1, 1), ('Page Up', 1, 1), ('About', 1, 1)],
    # Row 4: ASDF row (User Modified previously)
    [('Caps Lock', 1, 2), ('A', 1, 1), ('S', 1, 1), ('D', 1, 1), ('F', 1, 1), ('G', 1, 1), ('H', 1, 1), ('J', 1, 1), ('K', 1, 1), ('L', 1, 1), (';', 1, 1), ("'", 1, 1), ('Enter', 1, 2), None, ('Delete', 1, 1), ('End', 1, 1), ('Page Down', 1, 1), ('Set', 1, 1)], # Replaced Donate with None
    # Row 5: ZXCV row (User Modified previously)
    [('LShift', 1, 3), ('Z', 1, 1), ('X', 1, 1), ('C', 1, 1), ('V', 1, 1), ('B', 1, 1), ('N', 1, 1), ('M', 1, 1), (',', 1, 1), ('.', 1, 1), ('/', 1, 1), ('RShift', 1, 3), None, ('Up', 1, 1), None, None ],
    # Row 6: Bottom row (User Modified previously, Donate added here)
    [('L Ctrl', 1, 2), ('L Win', 1, 1), ('L Alt', 1, 1), ('Space', 1, 7), ('R Alt', 1, 1), ('R Win', 1, 1), ('App', 1, 1), ('R Ctrl', 1, 2), ('Left', 1, 1), ('Down', 1, 1), ('Right', 1, 1), ('Donate', 1, 1)] # Replaced last None with Donate
]
# --- نهاية التحديث ---
