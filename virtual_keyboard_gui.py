# -*- coding: utf-8 -*-
# file:virtual_keyboard_gui.py
# PyXKeyboard v1.0.6 - A simple, customizable on-screen virtual keyboard.
# Features include X11 key simulation (XTEST), system layout switching (XKB),
# visual layout updates, configurable appearance (fonts, colors, opacity, styles),
# auto-repeat, system tray integration, and optional AT-SPI based auto-show.
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.
# Contains the main VirtualKeyboard class, UI, event handling, and integration logic.
# --- Modified to load layout definitions from JSON files based on system config ---
# --- Fixed missing update_tray_menu_check_state ---
# --- Fixed Win/App key handling ---
# --- Refactored update_key_labels for correct Shift/Caps state & layout loading ---
# --- Fixed text color application when using system colors ---
# --- Corrected JSON loading validation and label update logic for null ---

import sys
import os
from typing import Optional, Tuple, Dict, List, Union # Added List, Union
import re
import copy
import webbrowser
from pathlib import Path
import json # Required for loading layout files

try:
    # Import necessary PyQt6 modules
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QPushButton, QGridLayout, QSizePolicy,
        QSystemTrayIcon, QMenu, QMessageBox
    )
    from PyQt6.QtCore import Qt, QSize, QEvent, QPoint, QTimer, pyqtSignal, QRect, QMetaObject, pyqtSlot
    from PyQt6.QtGui import (
        QFont, QPalette, QColor, QIcon, QAction,
        QPixmap, QPainter, QFontMetrics, QScreen,
        QActionGroup, QPen, QBrush, QCursor
    )
    from PyQt6.QtWidgets import QStyle
except ImportError:
    print("ERROR: PyQt6 library is required for the main GUI.")
    print("Please install it: pip install PyQt6")
    raise

# --- Local Project Imports (Relative Imports) ---
from .settings_manager import load_settings, save_settings, DEFAULT_SETTINGS
from .settings_dialog import SettingsDialog
from .key_definitions import KEYBOARD_LAYOUT, X11_KEYSYM_MAP, FALLBACK_CHAR_MAP # Import Fallback Map
from . import xlib_integration as xlib_int

if not xlib_int.is_dummy():
    import Xlib
    from Xlib import X
else:
    Xlib = None

from .xlib_integration import X as X_CONST
from .XKB_Switcher import XKBManager, XKBManagerError

_focus_monitor_available = False
try:
    from .focus_monitor import EditableFocusMonitor
    _focus_monitor_available = True
    print("Focus monitor module loaded successfully.")
except ImportError as e:
    print(f"WARNING: Could not import EditableFocusMonitor: {e}")
    EditableFocusMonitor = None
except Exception as e:
    print(f"WARNING: Unexpected error importing EditableFocusMonitor: {e}")
    EditableFocusMonitor = None

EDGE_NONE = 0; EDGE_TOP = 1; EDGE_BOTTOM = 2; EDGE_LEFT = 4; EDGE_RIGHT = 8
EDGE_TOP_LEFT = EDGE_TOP | EDGE_LEFT; EDGE_TOP_RIGHT = EDGE_TOP | EDGE_RIGHT
EDGE_BOTTOM_LEFT = EDGE_BOTTOM | EDGE_LEFT; EDGE_BOTTOM_RIGHT = EDGE_BOTTOM | EDGE_RIGHT


class VirtualKeyboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python XKeyboard")
        self.settings = load_settings()

        self.is_frameless = self.settings.get("frameless_window", DEFAULT_SETTINGS.get("frameless_window", False))
        self.always_on_top = self.settings.get("always_on_top", DEFAULT_SETTINGS.get("always_on_top", True))
        self.is_sticky = self.settings.get("sticky_on_all_workspaces", DEFAULT_SETTINGS.get("sticky_on_all_workspaces", False))
        self.use_system_colors = self.settings.get("use_system_colors", DEFAULT_SETTINGS.get("use_system_colors", False))

        self.app_font = QFont()
        self.load_initial_font_settings()
        xlib_int.initialize_xlib(); self.xlib_ok = xlib_int.is_xtest_ok(); self.is_xlib_dummy = xlib_int.is_dummy()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        base_flags = Qt.WindowType.Window | Qt.WindowType.WindowDoesNotAcceptFocus
        if self.always_on_top: base_flags |= Qt.WindowType.WindowStaysOnTopHint
        if self.is_frameless: base_flags |= Qt.WindowType.FramelessWindowHint
        else: base_flags |= (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)
        self.setWindowFlags(base_flags)


        self.resizing = False; self.resize_edge = EDGE_NONE; self.resize_start_pos = None; self.resize_start_geom = None
        self.resize_margin = 4
        self.setMouseTracking(True)
        self.buttons = {}; self.current_language = 'us'; # Start with a default like 'us'
        self.shift_pressed = False; self.ctrl_pressed = False; self.alt_pressed = False; self.caps_lock_pressed = False
        self.drag_position = None; self.xkb_manager = None; self.tray_icon = None; self.icon = None; self.language_menu = None; self.language_actions = {}; self.lang_action_group = None
        self.focus_monitor = None; self.focus_monitor_available = _focus_monitor_available
        self.tray_menu = None
        self.monitor_was_running_for_context_menu = False
        self.layout_check_timer = None

        self.loaded_layouts: Dict[str, Dict[str, Union[list, tuple]]] = {} # Type hint correction
        self.layouts_dir = os.path.join(os.path.dirname(__file__), 'layouts')
        # Layouts are loaded after XKB Manager initialization

        self.icon = self.load_app_icon()

        self.repeating_key_name = None
        self.initial_delay_timer = QTimer(self); self.initial_delay_timer.setSingleShot(True); self.initial_delay_timer.timeout.connect(self._trigger_initial_repeat)
        self.auto_repeat_timer = QTimer(self); self.auto_repeat_timer.timeout.connect(self._trigger_subsequent_repeat)
        self._update_repeat_timers_from_settings()

        self.init_xkb_manager() # This now loads layouts based on system config
        self.central_widget = QWidget(); self.central_widget.setObjectName("centralWidget"); self.central_widget.setMouseTracking(True); self.central_widget.setAutoFillBackground(True)
        self.setCentralWidget(self.central_widget); self.grid_layout = QGridLayout(self.central_widget); self.grid_layout.setSpacing(3); self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.init_focus_monitor()
        self._apply_global_styles_and_font()
        self.init_ui() # Creates buttons

        if self.icon: self.setWindowIcon(self.icon)
        self.init_tray_icon() # Setup tray after buttons potentially exist
        self.apply_initial_geometry()

        # Set initial language correctly *after* UI and XKB Manager are initialized
        initial_lang = self.xkb_manager.get_current_layout_name() if self.xkb_manager else None
        if not initial_lang or (initial_lang not in self.loaded_layouts and initial_lang not in ['us', 'en']):
             if 'us' in self.loaded_layouts: initial_lang = 'us'
             elif 'en' in self.loaded_layouts: initial_lang = 'en'
             elif self.loaded_layouts: initial_lang = next(iter(self.loaded_layouts))
             else: initial_lang = 'us'
        self.sync_vk_lang_with_system_slot(initial_lang) # Sync visuals with initial lang

        # Sticky state application removed
        # QTimer.singleShot(100, lambda: self._set_sticky_state(self.is_sticky))

    # --- *** تعديل: دالة تحميل ملفات التخطيط المطلوبة *** ---
    def _load_layout_files(self, required_layout_codes: List[str]):
        """Loads required .json layout files from the layouts directory."""
        print(f"Loading required layouts ({required_layout_codes}) from: {self.layouts_dir}")
        if not os.path.isdir(self.layouts_dir):
            print(f"Warning: Layouts directory not found: {self.layouts_dir}")
            return

        self.loaded_layouts = {} # Clear previous layouts

        # --- Always try to load fallback layouts first ---
        fallback_codes_to_try = ['us', 'en']
        loaded_fallback = None
        for code in fallback_codes_to_try:
             filepath = os.path.join(self.layouts_dir, f"{code}.json")
             if os.path.exists(filepath):
                  if self._load_single_layout_file(code, filepath):
                       print(f"  - Loaded essential fallback layout '{code}'.")
                       loaded_fallback = code # Remember which fallback was loaded
                       break # Load only one primary fallback (prefer 'us')

        if not loaded_fallback and not FALLBACK_CHAR_MAP:
             print("ERROR: No fallback layout (us.json/en.json) found and FALLBACK_CHAR_MAP is empty!", file=sys.stderr)
             # Application might be unusable without any base layout

        # --- Load layouts required by the system ---
        for layout_code in required_layout_codes:
            if layout_code in self.loaded_layouts: # Don't reload if it was the fallback
                 continue
            filepath = os.path.join(self.layouts_dir, f"{layout_code}.json")
            if os.path.exists(filepath):
                self._load_single_layout_file(layout_code, filepath)
            else:
                print(f"  - Warning: Layout file '{layout_code}.json' not found for system layout '{layout_code}'. Display will use fallback.")

    def _load_single_layout_file(self, layout_code: str, filepath: str) -> bool:
        """Loads and validates a single JSON layout file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                layout_data = json.load(f)
                if isinstance(layout_data, dict):
                    valid = True
                    for k, v in layout_data.items():
                        if not isinstance(k, str) or \
                           not isinstance(v, (list, tuple)) or \
                           not (1 <= len(v) <= 2) or \
                           not isinstance(v[0], str) or \
                           (len(v) == 2 and not isinstance(v[1], (str, type(None)))):
                            print(f"  - Warning: Invalid data structure for key '{k}' in {os.path.basename(filepath)} (value: {v}). Skipping file.", file=sys.stderr)
                            valid = False
                            break
                    if valid:
                        self.loaded_layouts[layout_code] = layout_data
                        print(f"  - Loaded layout data for '{layout_code}' from {os.path.basename(filepath)}")
                        return True
                else:
                    print(f"  - Warning: Invalid format in {os.path.basename(filepath)} (not a dictionary). Skipping.", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"  - Error decoding JSON in {os.path.basename(filepath)}: {e}. Skipping.", file=sys.stderr)
        except IOError as e:
            print(f"  - Error reading file {os.path.basename(filepath)}: {e}. Skipping.", file=sys.stderr)
        except Exception as e:
            print(f"  - Unexpected error loading {os.path.basename(filepath)}: {e}. Skipping.", file=sys.stderr)
        return False
    # --- *** نهاية التعديل *** ---

    def load_app_icon(self) -> Optional[QIcon]:
        icon = QIcon()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(script_dir, 'icons')
        icon_files = [
            os.path.join(icon_dir, "icon_32.png"), os.path.join(icon_dir, "icon_64.png"),
            os.path.join(icon_dir, "icon_128.png"), os.path.join(icon_dir, "icon_256.png"),
        ]
        found_any = False
        for file_path in icon_files:
            if os.path.exists(file_path): icon.addFile(file_path); found_any = True
        if found_any: print("Icon loaded successfully."); return icon
        else: print("No icon files found. Generating default."); return self.generate_keyboard_icon()

    def generate_keyboard_icon(self, size=32):
        pixmap = QPixmap(size, size); pixmap.fill(Qt.GlobalColor.transparent); painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body_color = QColor("#ADD8E6"); border_color = QColor("#607B8B"); key_color = QColor("#404040")
        body_rect_margin = int(size * 0.1); body_rect = pixmap.rect().adjusted(body_rect_margin, body_rect_margin, -body_rect_margin, -body_rect_margin)
        key_width_f = body_rect.width() * 0.18; key_height_f = body_rect.height() * 0.18; key_h_spacing_f = body_rect.width() * 0.07; key_v_spacing_f = body_rect.height() * 0.09
        base_x_f = body_rect.left() + key_h_spacing_f * 1.5; base_y_f = body_rect.top() + key_v_spacing_f * 1.5
        painter.setBrush(QBrush(body_color)); painter.setPen(QPen(border_color, max(1, int(size * 0.05)))); painter.drawRoundedRect(body_rect, size * 0.1, size * 0.1)
        painter.setBrush(QBrush(key_color)); painter.setPen(Qt.PenStyle.NoPen)
        for r in range(2):
            for c in range(3): key_x = base_x_f + c * (key_width_f + key_h_spacing_f); key_y = base_y_f + r * (key_height_f + key_v_spacing_f); painter.drawRect(int(key_x), int(key_y), int(key_width_f), int(key_height_f))
        space_y = base_y_f + 2 * (key_height_f + key_v_spacing_f); space_width = key_width_f * 2 + key_h_spacing_f; painter.drawRect(int(base_x_f), int(space_y), int(space_width), int(key_height_f))
        painter.end(); return QIcon(pixmap)

    def _update_repeat_timers_from_settings(self):
        delay_ms = self.settings.get("auto_repeat_delay_ms", DEFAULT_SETTINGS.get("auto_repeat_delay_ms", 1500))
        interval_ms = self.settings.get("auto_repeat_interval_ms", DEFAULT_SETTINGS.get("auto_repeat_interval_ms", 100))
        self.initial_delay_timer.setInterval(delay_ms)
        self.auto_repeat_timer.setInterval(interval_ms)

    def load_initial_font_settings(self):
        font_family = self.settings.get("font_family", DEFAULT_SETTINGS.get("font_family", "Sans Serif"));
        font_size = self.settings.get("font_size", DEFAULT_SETTINGS.get("font_size", 9))
        try:
            self.app_font.setFamily(font_family); self.app_font.setPointSize(font_size); print(f"Loaded font: {self.app_font.family()} {self.app_font.pointSize()}pt")
        except Exception as e:
            print(f"ERROR creating font: {e}. Using default."); self.app_font.setFamily(DEFAULT_SETTINGS.get("font_family", "Sans Serif")); self.app_font.setPointSize(DEFAULT_SETTINGS.get("font_size", 9))

    def apply_initial_geometry(self):
        initial_geom_applied = False; min_width, min_height = 400, 130
        if self.settings.get("remember_geometry", DEFAULT_SETTINGS.get("remember_geometry", True)):
            geom = self.settings.get("window_geometry")
            if geom and isinstance(geom, dict) and all(k in geom for k in ["x", "y", "width", "height"]):
                try:
                    width = max(min_width, geom["width"]); height = max(min_height, geom["height"]); print(f"Applying saved geometry: x={geom['x']}, y={geom['y']}, w={width}, h={height}")
                    self.setGeometry(geom["x"], geom["y"], width, height); initial_geom_applied = True
                except Exception as e: print(f"ERROR applying saved geometry: {e}."); self.settings["window_geometry"] = None
            else:
                 print("Ignoring invalid saved geometry.")
                 self.settings["window_geometry"] = None
        if not initial_geom_applied: print("Applying default geometry."); self.resize(900, 180); self.center_window()
        self.setMinimumSize(min_width, min_height)

    def init_xkb_manager(self):
        """Initializes the XKBManager, loads corresponding layouts, and starts monitoring/timer."""
        self.xkb_manager = None
        if self.layout_check_timer and self.layout_check_timer.isActive():
            self.layout_check_timer.stop()
        self.layout_check_timer = None

        system_layouts = [] # Default to empty list

        try:
            self.xkb_manager = XKBManager(auto_refresh=True, start_monitoring=False)

            if self.xkb_manager and self.xkb_manager.get_current_method() != XKBManager.METHOD_NONE:
                system_layouts = self.xkb_manager.get_available_layouts()
                print(f"System layouts detected: {system_layouts}")

                # Load layout files corresponding to system layouts AFTER manager is initialized
                self._load_layout_files(system_layouts)

                self.xkb_manager.layoutChanged.connect(self.sync_vk_lang_with_system_slot, Qt.ConnectionType.QueuedConnection)

                if self.xkb_manager.can_monitor():
                    print("Starting xkb-switch monitoring...")
                    self.xkb_manager.start_change_monitor()
                else:
                    print("xkb-switch not available or failed, starting fallback timer...")
                    self.layout_check_timer = QTimer(self)
                    self.layout_check_timer.timeout.connect(self.check_system_layout_timer_slot)
                    self.layout_check_timer.start(1000)
            else:
                print("XKB Manager could not be initialized with any method. Loading default layouts only.")
                self._load_layout_files(['us', 'en', 'ar'])
                self.current_language = 'us' # Fallback language

        except (XKBManagerError, Exception) as e:
            print(f"XKBManager Initialization FAILED: {e}", file=sys.stderr)
            self.xkb_manager = None
            print("Loading default layouts due to XKB Manager error.")
            self._load_layout_files(['us', 'en', 'ar'])
            self.current_language = 'us'

    def init_focus_monitor(self):
        if not self.focus_monitor_available or not EditableFocusMonitor: print("Focus monitor skipped."); return
        try:
            self.focus_monitor = EditableFocusMonitor(self._handle_editable_focus); print("EditableFocusMonitor instance created.")
            if self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False)):
                print("Auto-show enabled, starting monitor..."); self.focus_monitor.start()
                if not self.focus_monitor.is_running(): print("WARNING: Could not start focus monitor.")
            else: print("Auto-show disabled.")
        except Exception as e: print(f"ERROR initializing focus monitor: {e}"); self.focus_monitor = None; self.focus_monitor_available = False

    def _handle_editable_focus(self, accessible):
        if self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False)):
            if self.isHidden():
                print("Editable field focused, showing keyboard...")
                QTimer.singleShot(50, self.show_normal_and_raise)

    def show_normal_and_raise(self):
        if self.isHidden(): self.showNormal(); self.raise_()

    def _apply_global_styles_and_font(self):
        """Applies styles based on settings, handling system colors and custom colors."""
        if not self.central_widget: return
        use_system_colors = self.settings.get("use_system_colors", DEFAULT_SETTINGS.get("use_system_colors", False))
        custom_text_color = self.settings.get("text_color", DEFAULT_SETTINGS.get("text_color", "#FFFFFF"))
        button_style_name = self.settings.get("button_style", DEFAULT_SETTINGS.get("button_style", "default"))
        opacity_level = self.settings.get("window_opacity", DEFAULT_SETTINGS.get("window_opacity", 1.0))
        font_family = self.app_font.family(); font_size = self.app_font.pointSize()
        window_bg_color_setting = self.settings.get("window_background_color", DEFAULT_SETTINGS.get("window_background_color", "#F0F0F0"))
        button_bg_color_setting = self.settings.get("button_background_color", DEFAULT_SETTINGS.get("button_background_color", "#E1E1E1"))

        # --- Use the custom text color setting directly ---
        final_text_color_str = custom_text_color
        try:
            final_text_qcolor = QColor(final_text_color_str)
            # print(f"Applying text color: {final_text_color_str}")
        except Exception:
            print(f"Warning: Invalid text color '{custom_text_color}'. Using default black.", file=sys.stderr)
            final_text_color_str = "#000000"
            final_text_qcolor = QColor(final_text_color_str)

        # --- Build base button style parts ---
        common_button_style_parts = [
            f"color: {final_text_color_str};", # Always apply text color via CSS first
            f"font-family: '{font_family}';",
            f"font-size: {font_size}pt;",
            "padding: 2px;"
        ]

        button_specific_style_parts = []
        base_button_style = ""

        if not use_system_colors:
            # --- Apply custom styles if not using system theme ---
            if button_style_name == "flat":
                button_specific_style_parts.extend([
                    f"background-color: {button_bg_color_setting};",
                    "border: 1px solid #aaaaaa;", "border-radius: 3px;" ])
            elif button_style_name == "gradient":
                button_specific_style_parts.extend([
                    "border: 1px solid #bbbbbb;",
                    """background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #fefefe, stop: 1 #e0e0e0);""",
                    "border-radius: 4px;" ])
            else: # default style with custom colors
                button_specific_style_parts.append(f"background-color: {button_bg_color_setting};")
                button_specific_style_parts.append("border: 1px solid #C0C0C0;")
            base_button_style = " ".join(common_button_style_parts + button_specific_style_parts)
        else:
            # --- Use system theme (only common parts applied in base) ---
            button_specific_style_parts = []
            base_button_style = " ".join(common_button_style_parts)

        # --- Styles for special states/buttons ---
        toggled_modifier_style = "background-color: #a0cfeC !important; border: 1px solid #0000A0 !important; font-weight: bold;"
        custom_control_style = "font-weight: bold; font-size: 10pt;"
        donate_style = "font-size: 10pt; font-weight: bold; background-color: yellow; color: black !important; border: 1px solid #A0A000;" # Force black color for donate

        # --- Apply window background ---
        alpha_value = int(max(0.0, min(1.0, opacity_level)) * 255)
        final_window_bg_rgba = "rgba(0,0,0,0)"

        if not use_system_colors:
            try:
                base_window_color = QColor(window_bg_color_setting)
                final_window_bg_rgba = f"rgba({base_window_color.red()}, {base_window_color.green()}, {base_window_color.blue()}, {alpha_value})"
            except Exception as e: print(f"Error applying custom window background color '{window_bg_color_setting}': {e}")
        else:
             palette = self.palette()
             base_color = palette.color(QPalette.ColorRole.Window)
             final_window_bg_rgba = f"rgba({base_color.red()}, {base_color.green()}, {base_color.blue()}, {alpha_value})"

        bg_style = f"background-color: {final_window_bg_rgba} !important;"
        # Ensure the central widget gets the background color
        self.central_widget.setStyleSheet(f"QWidget#centralWidget {{ {bg_style} }}")
        # Also set autoFillBackground - might help with themes
        self.central_widget.setAutoFillBackground(True)


        # --- Apply final stylesheet to the main window ---
        full_stylesheet = f"""
            QPushButton {{ {base_button_style} }}
            /* Explicitly set text color again for higher specificity if needed */
            QPushButton {{ color: {final_text_color_str}; }}
            QPushButton:pressed {{ background-color: #cceeff !important; border: 1px solid #88aabb !important; }}
            QPushButton[modifier_on="true"] {{ {toggled_modifier_style} }}
            QPushButton#MinimizeButton, QPushButton#CloseButton {{ {custom_control_style} color: {final_text_color_str}; }} /* Ensure text color */
            QPushButton#DonateButton {{ {donate_style} }}
        """
        self.setStyleSheet(full_stylesheet)

        # --- Palette application removed, relying on CSS ---

    def update_application_font(self, new_font): self.app_font = QFont(new_font)
    def update_application_opacity(self, opacity_level): self.settings["window_opacity"] = max(0.0, min(1.0, opacity_level))
    def update_application_text_color(self, color_str):
        if not (isinstance(color_str, str) and color_str.startswith('#') and (len(color_str) == 7 or len(color_str) == 9)):
            color_str = DEFAULT_SETTINGS.get("text_color", "#000000")
        self.settings["text_color"] = color_str

    def update_window_background_color(self, color_str):
        if not (isinstance(color_str, str) and color_str.startswith('#') and (len(color_str) == 7 or len(color_str) == 9)):
            color_str = DEFAULT_SETTINGS.get("window_background_color", "#F0F0F0")
        self.settings["window_background_color"] = color_str

    def update_button_background_color(self, color_str):
        if not (isinstance(color_str, str) and color_str.startswith('#') and (len(color_str) == 7 or len(color_str) == 9)):
            color_str = DEFAULT_SETTINGS.get("button_background_color", "#E1E1E1")
        self.settings["button_background_color"] = color_str

    def update_application_button_style(self, style_name):
        valid_styles = ["default", "flat", "gradient"];
        if style_name not in valid_styles: style_name = DEFAULT_SETTINGS.get("button_style", "default")
        self.settings["button_style"] = style_name

    def center_window(self):
        try:
            screen = QApplication.primaryScreen()
            if screen:
                available_geom = screen.availableGeometry()
                center_point = available_geom.center()
                frame_geo = self.frameGeometry()
                top_left = center_point - frame_geo.center() + frame_geo.topLeft()
                top_left.setX(max(available_geom.left(), top_left.x()))
                top_left.setY(max(available_geom.top(), top_left.y()))
                self.move(top_left)
            else: print("WARNING: Could not get primary screen info to center window.")
        except Exception as e: print(f"WARNING: Error centering window: {e}")

    def init_ui(self):
        symbol_map = { "Caps Lock": "⇪ Caps", "Tab": "⇥ Tab", "Enter": "↵ Enter", "Backspace": "⌫ Bksp", "Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "L Win": "◆", "R Win": "◆", "App": "☰", "Scroll Lock": "Scroll Lk", "Pause": "Pause", "PrtSc":"PrtSc", "Insert":"Ins", "Home":"Home", "Page Up":"PgUp", "Delete":"Del", "End":"End", "Page Down":"PgDn", "L Ctrl":"Ctrl", "R Ctrl":"Ctrl", "L Alt":"Alt", "R Alt":"AltGr", "Space":"Space", "Esc":"Esc", "About":"About", "Set":"Set", "LShift": "⇧ Shift", "RShift": "⇧ Shift", "Minimize":"_", "Close":"X", "Donate":"Donate"}
        self.buttons = {}
        while self.grid_layout.count():
             item = self.grid_layout.takeAt(0)
             if item is not None: widget = item.widget();
             if widget: widget.deleteLater()

        repeatable_keys = set(FALLBACK_CHAR_MAP.keys()) | {'Space', 'Backspace', 'Delete', 'Tab', 'Enter', 'Up', 'Down', 'Left', 'Right'}
        non_repeatable_functional_keys = {'Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
                                           'PrtSc', 'Scroll Lock', 'Pause', 'Insert', 'Home', 'Page Up', 'End', 'Page Down',
                                           'L Win', 'R Win', 'App'}
        modifier_keys = {'LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock'}
        special_action_keys = {'About', 'Set', 'Minimize', 'Close', 'Donate', 'Lang'}

        for r, row_keys in enumerate(KEYBOARD_LAYOUT):
            col = 0
            for key_data in row_keys:
                if key_data:
                    key_name, row_span, col_span = key_data
                    initial_label = symbol_map.get(key_name, key_name)
                    if key_name.startswith("F") and key_name[1:].isdigit(): initial_label = key_name
                    elif key_name == "Lang": initial_label = "Lang"

                    button = QPushButton(initial_label)
                    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    button.setAutoRepeat(False)

                    if key_name in special_action_keys:
                        if key_name == 'Lang': button.clicked.connect(self.toggle_language)
                        elif key_name == 'About': button.clicked.connect(self.show_about_message)
                        elif key_name == 'Set': button.clicked.connect(self.open_settings_dialog)
                        elif key_name == 'Minimize': button.clicked.connect(self.hide_to_tray); button.setObjectName("MinimizeButton")
                        elif key_name == 'Close': button.clicked.connect(self.quit_application); button.setObjectName("CloseButton")
                        elif key_name == 'Donate': button.clicked.connect(self._open_donate_link); button.setObjectName("DonateButton")
                    elif key_name in modifier_keys:
                        button.setProperty("modifier_on", False)
                        button.clicked.connect(lambda chk=False, k=key_name: self.on_modifier_key_press(k))
                    elif key_name in repeatable_keys:
                        button.pressed.connect(lambda k=key_name: self._handle_key_pressed(k))
                        button.released.connect(lambda k=key_name: self._handle_key_released(k))
                        if key_name in FALLBACK_CHAR_MAP:
                            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                            button.customContextMenuRequested.connect(lambda pos, k=key_name: self.on_typable_key_right_press(k))
                    elif key_name in non_repeatable_functional_keys:
                        button.clicked.connect(lambda chk=False, k=key_name: self.on_non_repeatable_key_press(k))
                    else:
                        print(f"Warning: Key '{key_name}' has no defined action.")

                    self.grid_layout.addWidget(button, r, col, row_span, col_span)
                    self.buttons[key_name] = button
                    if key_name in ['Minimize', 'Close']:
                         button.setVisible(self.is_frameless)

                    col += col_span
                else:
                    col += 1
        # Initial sync is now handled in __init__

    def _open_donate_link(self):
        url = "https://paypal.me/kh1512"; print(f"Opening donation link: {url}")
        try: webbrowser.open_new_tab(url)
        except Exception as e: print(f"ERROR opening donation link: {e}"); QMessageBox.warning(self, "Link Error", f"Could not open donation link:\n{url}\n\nError: {e}")

    def hide_to_tray(self):
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            try:
                 self.tray_icon.showMessage(self.windowTitle(), "Minimized to system tray.", self.icon if self.icon else QIcon(), 2000)
            except Exception as e: print(f"Tray message failed: {e}")
        elif not self.is_frameless: print("No tray, minimizing."); self.showMinimized()
        else: print("No tray and frameless, hiding window."); self.hide()

    def init_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            if self.tray_icon: self.tray_icon.hide(); self.tray_icon = None
            self.tray_menu = None; print("System Tray not available."); return
        if not self.tray_icon:
            self.tray_icon = QSystemTrayIcon(self)
            try:
                if self.icon: self.tray_icon.setIcon(self.icon)
            except Exception as e: print(f"Tray icon error: {e}")
            self.tray_icon.activated.connect(self.tray_icon_activated); print("System tray icon created.")
        else:
            if self.icon and self.tray_icon.icon().cacheKey() != self.icon.cacheKey():
                 try: print("Updating tray icon..."); self.tray_icon.setIcon(self.icon)
                 except Exception as e: print(f"Tray icon update error: {e}")

        if self.tray_menu: self.tray_menu.clear()
        self.tray_menu = QMenu(self); self.language_menu = None; self.language_actions = {}; self.lang_action_group = None

        if self.xkb_manager:
            layouts = self.xkb_manager.get_available_layouts()
            if layouts and len(layouts) > 1:
                self.language_menu = QMenu("Select Layout", self); self.lang_action_group = QActionGroup(self); self.lang_action_group.setExclusive(True)
                for lc in layouts: a = QAction(lc, self, checkable=True); a.triggered.connect(lambda checked=False, l=lc: self.set_system_language_from_menu(l)); self.language_menu.addAction(a); self.language_actions[lc] = a; self.lang_action_group.addAction(a)
                self.tray_menu.addMenu(self.language_menu); self.tray_menu.addSeparator()

        about_action = QAction("About...", self); about_action.triggered.connect(self.show_about_message)
        settings_action = QAction("Settings...", self); settings_action.triggered.connect(self.open_settings_dialog)
        self.tray_menu.addActions([about_action, settings_action])
        donate_action = QAction("Donate...", self)
        donate_action.triggered.connect(self._open_donate_link)
        self.tray_menu.addAction(donate_action)
        self.tray_menu.addSeparator()
        show_act = QAction("Show Keyboard", self); show_act.triggered.connect(self.show_normal_and_raise)
        hide_act = QAction("Hide (Middle Mouse Click)", self); hide_act.setEnabled(self.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True))); hide_act.triggered.connect(self.hide_to_tray)
        self.tray_menu.addActions([show_act, hide_act]); self.tray_menu.addSeparator()
        quit_act = QAction("Quit", self); quit_act.triggered.connect(self.quit_application)
        self.tray_menu.addAction(quit_act); self.tray_icon.setContextMenu(self.tray_menu)

        if not self.tray_icon.isVisible():
             try: self.tray_icon.show()
             except Exception as e: print(f"Tray show error: {e}")

        tooltip_parts = [self.windowTitle()]
        if self.xkb_manager: tooltip_parts.append(f"Layout: {self.xkb_manager.get_current_layout_name() or 'N/A'}")
        if not self.xlib_ok: tooltip_parts.append("Input ERR")
        if self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False)): tooltip_parts.append("AutoShow ON")
        if self.always_on_top: tooltip_parts.append("Always On Top")
        try: self.tray_icon.setToolTip("\n".join(tooltip_parts))
        except Exception as e: print(f"Tray tooltip error: {e}")
        self.update_tray_menu_check_state()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: self.show_normal_and_raise()

    def show_normal_and_activate(self):
        if self.isHidden(): self.showNormal(); self.activateWindow(); self.raise_()

    def closeEvent(self, event):
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide_to_tray()
        else:
            event.accept()
            self.quit_application()

    def quit_application(self):
        print("Quit requested...")
        if self.xkb_manager and self.xkb_manager.can_monitor():
            self.xkb_manager.stop_change_monitor()
        elif self.layout_check_timer and self.layout_check_timer.isActive():
            self.layout_check_timer.stop()
        if hasattr(self, 'initial_delay_timer'): self.initial_delay_timer.stop()
        if hasattr(self, 'auto_repeat_timer'): self.auto_repeat_timer.stop()
        if self.focus_monitor and self.focus_monitor.is_running():
            try: self.focus_monitor.stop()
            except Exception as e: print(f"Error stopping focus monitor: {e}")
        if self.settings.get("remember_geometry", DEFAULT_SETTINGS.get("remember_geometry", True)):
            try:
                if not self.isMinimized():
                     self.settings["window_geometry"] = {"x": self.geometry().x(),"y": self.geometry().y(),"width": self.geometry().width(),"height": self.geometry().height()}
            except Exception as e: self.settings["window_geometry"] = None; print(f"ERROR getting geometry: {e}")
        else: self.settings["window_geometry"] = None
        save_settings(self.settings);
        if self.tray_icon: self.tray_icon.hide()
        xlib_int.close_xlib(); print("Quitting application...")
        instance = QApplication.instance();
        if instance: instance.quit()

    def show_about_message(self):
        program_name = self.windowTitle(); monitor_was_running = False
        if self.focus_monitor and self.focus_monitor.is_running():
            print("Pausing focus monitor for About dialog...");
            try: self.focus_monitor.stop(); monitor_was_running = True
            except Exception as e: print(f"ERROR stopping focus monitor: {e}")
        try:
            status_xkb="N/A"; status_xtest="N/A"; status_auto_show="N/A"
            xkb_method = f" ({self.xkb_manager.get_current_method()})" if self.xkb_manager else ""
            if XKBManager is None: status_xkb = "Disabled (XKB_Switcher missing)"
            elif self.xkb_manager: status_xkb = f"Enabled{xkb_method} (Layouts: {', '.join(self.xkb_manager.get_available_layouts() or ['N/A'])})"
            else: status_xkb = "Disabled (Init error)"
            if self.is_xlib_dummy: status_xtest = "Disabled (python-xlib missing)"
            elif self.xlib_ok: status_xtest = "Enabled"
            else: status_xtest = "Disabled (Init error)"
            if not self.focus_monitor_available: status_auto_show = "Disabled (AT-SPI unavailable)"
            else:
                 setting_enabled = self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
                 if self.focus_monitor and setting_enabled: is_currently_active = monitor_was_running or (self.focus_monitor and self.focus_monitor.is_running()); status_auto_show = "Enabled (Active)" if is_currently_active else "Enabled (Inactive)"
                 elif setting_enabled: status_auto_show = "Enabled (Inactive - Init Failed?)"
                 else: status_auto_show = "Disabled (in Settings)"

            script_dir = os.path.dirname(os.path.abspath(__file__))
            badge_icon_path_relative = os.path.join('icons', 'icon_64.png')
            badge_icon_path_full = os.path.join(script_dir, badge_icon_path_relative)
            badge_html = ""
            if os.path.exists(badge_icon_path_full):
                try:
                    badge_uri = Path(badge_icon_path_full).as_uri()
                    badge_html = f'<img src="{badge_uri}" alt="App Icon" width="64" height="64" style="float: left; margin-right: 10px; margin-bottom: 10px;">'
                except Exception as uri_e:
                     print(f"Error creating file URI for badge: {uri_e}")
                     badge_html = f'<img src="{badge_icon_path_relative}" alt="Icon" width="64" height="64" style="float: left; margin-right: 10px; margin-bottom: 10px;">'
            else:
                print(f"Badge icon not found: {badge_icon_path_full}")

            main_info = f"""
             {badge_html}
             <div style="overflow: hidden;">
             <p><b>{program_name} v1.0.6</b><br>A simple on-screen virtual keyboard.</p>
             <p>Developed by: Khaled Abdelhamid<br>Contact: <a href="mailto:khaled1512@gmail.com">khaled1512@gmail.com</a></p>
             <p><b>License:</b><br>GNU General Public License v3 (GPLv3)</p>
             <p><b>Disclaimer:</b><br>Provided 'as is'. Use at your own risk.</p>
             <p>Support development via PayPal:<br><a href="https://paypal.me/kh1512">https://paypal.me/kh1512</a><br>(Copy: <code>paypal.me/kh1512</code>)</p>
             <p>Thank you!</p>
             </div>
             <div style="clear: both;"></div>
             """
            full_message = main_info + "<hr>" + f"""<p><b>Status:</b><br>Layout Control (XKB): {status_xkb}<br>Input Simulation (XTEST): {status_xtest}<br>Auto-Show (AT-SPI): {status_auto_show}</p>"""
            QMessageBox.information(self, f"About {program_name}", full_message)
        finally:
            setting_is_enabled_after_dialog = self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
            if monitor_was_running and setting_is_enabled_after_dialog:
                print("Resuming focus monitor after About dialog...")
                if self.focus_monitor:
                    try:
                        if not self.focus_monitor.is_running(): self.focus_monitor.start()
                        if not self.focus_monitor.is_running(): print("WARNING: Could not resume monitor.")
                    except Exception as e: print(f"ERROR resuming focus monitor: {e}")
                else: print("Cannot resume focus monitor, instance is missing.")
            self.init_tray_icon()

    def open_settings_dialog(self):
        settings_copy = copy.deepcopy(self.settings); dialog = SettingsDialog(settings_copy, self.app_font, self.focus_monitor_available, self)
        dialog.settingsApplied.connect(self._apply_settings_from_dialog)
        monitor_was_running = False
        if self.focus_monitor and self.focus_monitor.is_running():
            print("Pausing focus monitor for Settings dialog...");
            try: self.focus_monitor.stop(); monitor_was_running = True
            except Exception as e: print(f"ERROR stopping focus monitor: {e}")
        try:
            dialog.exec()
        finally:
            setting_is_enabled_after_dialog = self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
            if monitor_was_running and setting_is_enabled_after_dialog:
                print("Resuming focus monitor after Settings dialog...")
                if self.focus_monitor:
                    try:
                        if not self.focus_monitor.is_running(): self.focus_monitor.start()
                        if not self.focus_monitor.is_running(): print("WARNING: Could not resume.")
                    except Exception as e: print(f"ERROR resuming focus monitor: {e}")
                else: print("Cannot resume focus monitor.")
            elif monitor_was_running and not setting_is_enabled_after_dialog:
                print("Not resuming disabled focus monitor after Settings dialog.")
                if self.focus_monitor and self.focus_monitor.is_running():
                     try: self.focus_monitor.stop()
                     except Exception as e: print(f"ERROR stopping disabled focus monitor: {e}")
            self.init_tray_icon()
            try: dialog.settingsApplied.disconnect(self._apply_settings_from_dialog)
            except (TypeError, RuntimeError): pass

    def _set_sticky_state(self, sticky: bool):
        """Sets the window's sticky state using Xlib EWMH hints."""
        if self.is_xlib_dummy or not Xlib: return
        display = xlib_int.get_display()
        if not display: return
        try:
            win_id = self.winId()
            if not win_id: QTimer.singleShot(200, lambda: self._set_sticky_state(sticky)); return
            NET_WM_STATE = display.intern_atom('_NET_WM_STATE')
            NET_WM_STATE_STICKY = display.intern_atom('_NET_WM_STATE_STICKY')
            if not NET_WM_STATE or not NET_WM_STATE_STICKY: print("Sticky state: Failed (EWMH atoms missing)"); return
            action = 1 if sticky else 0
            data = [action, NET_WM_STATE_STICKY, 0, 1, 0]
            root = display.screen().root
            event = Xlib.protocol.event.ClientMessage(window=win_id, client_type=NET_WM_STATE, data=(32, data))
            mask = (X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            root.send_event(event, event_mask=mask)
            display.flush()
        except Exception as e:
            print(f"Sticky state: ERROR applying - {e}", file=sys.stderr)
            try:
                if display: display.flush()
            except: pass

    def _apply_settings_from_dialog(self, applied_settings):
        """Applies settings received from the settings dialog."""
        print("Applying settings from dialog...");
        previous_frameless = self.is_frameless
        previous_on_top = self.always_on_top

        self.settings = copy.deepcopy(applied_settings)

        self.is_frameless = self.settings.get("frameless_window", DEFAULT_SETTINGS.get("frameless_window", False))
        self.always_on_top = self.settings.get("always_on_top", DEFAULT_SETTINGS.get("always_on_top", True))
        self.is_sticky = self.settings.get("sticky_on_all_workspaces", DEFAULT_SETTINGS.get("sticky_on_all_workspaces", False))
        self.use_system_colors = self.settings.get("use_system_colors", DEFAULT_SETTINGS.get("use_system_colors", False))

        self.update_window_background_color(self.settings.get("window_background_color", DEFAULT_SETTINGS.get("window_background_color", "#F0F0F0")))
        self.update_button_background_color(self.settings.get("button_background_color", DEFAULT_SETTINGS.get("button_background_color", "#E1E1E1")))

        new_font = QFont(self.settings.get("font_family", DEFAULT_SETTINGS.get("font_family", "Sans Serif")),
                         self.settings.get("font_size", DEFAULT_SETTINGS.get("font_size", 9)))
        if new_font != self.app_font:
            self.update_application_font(new_font)

        self.update_application_opacity(self.settings.get("window_opacity", DEFAULT_SETTINGS.get("window_opacity", 1.0)))
        self.update_application_text_color(self.settings.get("text_color", DEFAULT_SETTINGS.get("text_color", "#000000")))
        self.update_application_button_style(self.settings.get("button_style", DEFAULT_SETTINGS.get("button_style", "default")))
        self._update_repeat_timers_from_settings()

        flags_changed = (self.is_frameless != previous_frameless or self.always_on_top != previous_on_top)

        if flags_changed:
            print("Window flags changed, re-applying...")
            base_flags = Qt.WindowType.Window | Qt.WindowType.WindowDoesNotAcceptFocus
            if self.always_on_top: base_flags |= Qt.WindowType.WindowStaysOnTopHint
            if self.is_frameless: base_flags |= Qt.WindowType.FramelessWindowHint
            else: base_flags |= (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)

            current_visibility = self.isVisible()
            self.hide()
            self.setWindowFlags(base_flags)
            self._apply_global_styles_and_font() # Apply styles AFTER flags
            for key_name in ['Minimize', 'Close']:
                 if key_name in self.buttons: self.buttons[key_name].setVisible(self.is_frameless)
            print("Custom button visibility updated.")
            if current_visibility: QTimer.singleShot(50, self.show)
            else: print("Window was hidden, keeping hidden.")
        else:
            self._apply_global_styles_and_font() # Apply styles even if flags didn't change
            self.update_key_labels()
            print("Styles and labels updated (no flag change).")

        # Sticky state application removed

        self.init_tray_icon()


    def _resume_monitor_after_menu(self):
        print("Context menu closed.")
        try:
            if self.tray_menu: self.tray_menu.aboutToHide.disconnect(self._resume_monitor_after_menu)
        except (TypeError, RuntimeError): pass
        setting_is_enabled_after_menu = self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
        if self.monitor_was_running_for_context_menu and setting_is_enabled_after_menu:
            print("Resuming focus monitor after context menu...")
            if self.focus_monitor:
                try:
                    if not self.focus_monitor.is_running(): self.focus_monitor.start()
                    if not self.focus_monitor.is_running(): print("WARNING: Could not resume monitor.")
                except Exception as e: print(f"ERROR resuming focus monitor: {e}")
            else: print("Cannot resume focus monitor, instance is missing.")
        self.monitor_was_running_for_context_menu = False

    def _get_resize_edge(self, pos: QPoint) -> int:
        if not self.is_frameless: return EDGE_NONE
        rect = self.rect(); margin = self.resize_margin
        on_top = pos.y() < margin; on_bottom = pos.y() > rect.bottom() - margin
        on_left = pos.x() < margin; on_right = pos.x() > rect.right() - margin
        edge = EDGE_NONE
        if on_top: edge |= EDGE_TOP;
        if on_bottom: edge |= EDGE_BOTTOM
        if on_left: edge |= EDGE_LEFT;
        if on_right: edge |= EDGE_RIGHT
        return edge

    def _update_cursor_shape(self, edge: int):
        cursor_shape = Qt.CursorShape.ArrowCursor
        if self.is_frameless:
            if edge == EDGE_TOP or edge == EDGE_BOTTOM: cursor_shape = Qt.CursorShape.SizeVerCursor
            elif edge == EDGE_LEFT or edge == EDGE_RIGHT: cursor_shape = Qt.CursorShape.SizeHorCursor
            elif edge == EDGE_TOP_LEFT or edge == EDGE_BOTTOM_RIGHT: cursor_shape = Qt.CursorShape.SizeFDiagCursor
            elif edge == EDGE_TOP_RIGHT or edge == EDGE_BOTTOM_LEFT: cursor_shape = Qt.CursorShape.SizeBDiagCursor
        if self.cursor().shape() != cursor_shape: self.setCursor(QCursor(cursor_shape))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            if self.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True)):
                self.hide_to_tray(); event.accept(); return
        elif event.button() == Qt.MouseButton.RightButton:
            target_widget = self.childAt(event.position().toPoint())
            is_background_click = (target_widget is self or target_widget is self.central_widget or target_widget is None)
            if self.tray_menu and is_background_click:
                self.monitor_was_running_for_context_menu = False
                if self.focus_monitor and self.focus_monitor.is_running():
                    print("Pausing focus monitor for context menu...");
                    try: self.focus_monitor.stop(); self.monitor_was_running_for_context_menu = True
                    except Exception as e: print(f"ERROR stopping focus monitor: {e}")
                try: self.tray_menu.aboutToHide.disconnect(self._resume_monitor_after_menu)
                except (TypeError, RuntimeError): pass
                self.tray_menu.aboutToHide.connect(self._resume_monitor_after_menu)
                self.tray_menu.popup(event.globalPosition().toPoint()); event.accept(); return
        elif event.button() == Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()
            if self.is_frameless:
                self.resize_edge = self._get_resize_edge(local_pos)
                if self.resize_edge != EDGE_NONE:
                    self.resizing = True; self.resize_start_pos = event.globalPosition().toPoint(); self.resize_start_geom = self.geometry()
                    self._update_cursor_shape(self.resize_edge); print(f"Start resize: {self.resize_edge}"); event.accept(); return
            target_widget = self.childAt(local_pos)
            is_button = isinstance(target_widget, QPushButton) if target_widget else False
            is_background_click = (target_widget is self.central_widget or target_widget is None or target_widget is self) and not is_button
            if is_background_click:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft(); print("Start drag (Left Button)"); event.accept(); return

    def mouseMoveEvent(self, event):
        if self.repeating_key_name and self.buttons.get(self.repeating_key_name):
             button = self.buttons[self.repeating_key_name]
             if not button.rect().contains(button.mapFromGlobal(event.globalPosition().toPoint())):
                  self._handle_key_released(self.repeating_key_name, force_stop=True)
        if self.is_frameless and self.resizing and event.buttons() == Qt.MouseButton.LeftButton:
            current_pos = event.globalPosition().toPoint(); delta = current_pos - self.resize_start_pos; new_geom = QRect(self.resize_start_geom)
            if self.resize_edge & EDGE_TOP: new_geom.setTop(self.resize_start_geom.top() + delta.y())
            if self.resize_edge & EDGE_BOTTOM: new_geom.setBottom(self.resize_start_geom.bottom() + delta.y())
            if self.resize_edge & EDGE_LEFT: new_geom.setLeft(self.resize_start_geom.left() + delta.x())
            if self.resize_edge & EDGE_RIGHT: new_geom.setRight(self.resize_start_geom.right() + delta.x())
            min_w, min_h = self.minimumSize().width(), self.minimumSize().height()
            if new_geom.width() < min_w:
                if self.resize_edge & EDGE_LEFT: new_geom.setLeft(new_geom.right() - min_w)
                else: new_geom.setWidth(min_w)
            if new_geom.height() < min_h:
                if self.resize_edge & EDGE_TOP: new_geom.setTop(new_geom.bottom() - min_h)
                else: new_geom.setHeight(min_h)
            self.setGeometry(new_geom); event.accept(); return
        elif self.drag_position is not None and event.buttons() == Qt.MouseButton.LeftButton:
             new_pos = event.globalPosition().toPoint() - self.drag_position; self.move(new_pos); event.accept(); return
        elif self.is_frameless and not self.resizing and self.drag_position is None:
             current_edge = self._get_resize_edge(event.position().toPoint()); self._update_cursor_shape(current_edge)
        if not (self.is_frameless and (self.resizing or self.drag_position is not None)):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.repeating_key_name:
             self._handle_key_released(self.repeating_key_name, force_stop=True)
        if self.is_frameless and self.resizing and event.button() == Qt.MouseButton.LeftButton:
            self.resizing = False; self.resize_edge = EDGE_NONE; self.resize_start_pos = None; self.resize_start_geom = None; self.unsetCursor(); print("Resize finished"); event.accept(); return
        elif self.drag_position is not None and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None; print("Drag finished"); event.accept(); return
        elif self.is_frameless and not self.resizing and not event.buttons():
            self.unsetCursor()
        if not (self.is_frameless and (self.resizing or self.drag_position is not None) and event.button() == Qt.MouseButton.LeftButton):
            super().mouseReleaseEvent(event)

    @pyqtSlot(str)
    def sync_vk_lang_with_system_slot(self, new_layout_name: Optional[str] = None):
        """Slot to update the virtual keyboard when the layout changes."""
        # print(f"Syncing VK layout (triggered by {'monitor signal' if new_layout_name else 'timer/manual'})...")
        if not self.xkb_manager: return

        current_sys_name = new_layout_name if new_layout_name is not None else self.xkb_manager.query_current_layout_name()

        if current_sys_name:
            target_vk_lang = current_sys_name
            layout_exists = target_vk_lang in self.loaded_layouts
            if not layout_exists:
                 if target_vk_lang.startswith('en') and 'us' in self.loaded_layouts: target_vk_lang = 'us'; layout_exists = True
                 elif 'us' in self.loaded_layouts: target_vk_lang = 'us'; layout_exists = True
                 elif self.loaded_layouts: target_vk_lang = next(iter(self.loaded_layouts)); layout_exists = True

            if not layout_exists:
                 print(f"Error: No suitable layout found for system layout '{current_sys_name}' and no fallbacks ('us', 'en'). Cannot update display.", file=sys.stderr)
                 target_vk_lang = 'us'

            if self.current_language != target_vk_lang:
                print(f"Update visual layout: {self.current_language} -> {target_vk_lang}")
                self.current_language = target_vk_lang
                self.update_key_labels()

            if new_layout_name is None and self.xkb_manager.get_current_layout_name() != current_sys_name:
                 if current_sys_name in self.xkb_manager.get_available_layouts():
                     try:
                         sys_index = self.xkb_manager.get_available_layouts().index(current_sys_name)
                         self.xkb_manager._set_internal_index(sys_index, emit_signal=False)
                     except ValueError: pass
                 else:
                     print(f"Sync Warning: Queried layout '{current_sys_name}' not in known system layouts.", file=sys.stderr)
        else:
            print("WARNING: Could not query current system layout during sync.")

        self.update_tray_menu_check_state()

    @pyqtSlot()
    def check_system_layout_timer_slot(self):
        """Called only by the QTimer to periodically check the system layout."""
        if not self.xkb_manager or self.xkb_manager.can_monitor():
             if self.layout_check_timer and self.layout_check_timer.isActive():
                 self.layout_check_timer.stop()
             return

        current_sys_name = self.xkb_manager.query_current_layout_name()
        internal_name = self.xkb_manager.get_current_layout_name()

        if current_sys_name and current_sys_name != internal_name:
            print(f"Timer detected layout change: {current_sys_name}. Syncing...")
            self.sync_vk_lang_with_system_slot()

    def update_tray_menu_check_state(self):
        """Updates the check state of the language actions in the tray menu."""
        if not self.xkb_manager or not self.lang_action_group or not self.language_actions: return
        current_internal_name = self.xkb_manager.get_current_layout_name()
        if not current_internal_name: return

        action_to_check = self.language_actions.get(current_internal_name)
        checked_action = self.lang_action_group.checkedAction()

        if checked_action and checked_action != action_to_check:
            checked_action.blockSignals(True); checked_action.setChecked(False); checked_action.blockSignals(False)
        if action_to_check and not action_to_check.isChecked():
            action_to_check.blockSignals(True); action_to_check.setChecked(True); action_to_check.blockSignals(False)

    def toggle_language(self):
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        if not self.xkb_manager:
             codes = list(self.loaded_layouts.keys())
             if not codes: codes = ['us']
             try: idx = codes.index(self.current_language)
             except ValueError: idx = -1
             next_idx = (idx + 1) % len(codes)
             self.current_language = codes[next_idx]
             self.update_key_labels(); QMessageBox.information(self, "Layout Info", "XKB Manager unavailable."); return
        if len(self.xkb_manager.get_available_layouts()) <= 1:
             QMessageBox.information(self, "Layout Info", "Only one layout configured."); self.sync_vk_lang_with_system_slot(); return
        print("Toggling language...");
        if not self.xkb_manager.cycle_next_layout():
             QMessageBox.warning(self, "Layout Switch Failed", f"{self.xkb_manager.get_current_method()} command failed.")
        if not self.xkb_manager.can_monitor():
             QTimer.singleShot(50, self.sync_vk_lang_with_system_slot)

    def set_system_language_from_menu(self, lang_code):
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        if not self.xkb_manager: self.update_tray_menu_check_state(); return
        print(f"Tray: Setting layout to '{lang_code}'...");
        if not self.xkb_manager.set_layout_by_name(lang_code, update_system=True):
            QMessageBox.warning(self, "Layout Switch Failed", f"Could not switch to '{lang_code}' using {self.xkb_manager.get_current_method()}.");
        if not self.xkb_manager.can_monitor():
             QTimer.singleShot(50, self.sync_vk_lang_with_system_slot)

    def update_key_labels(self):
        symbol_map = { "Caps Lock": "⇪ Caps", "Tab": "⇥ Tab", "Enter": "↵ Enter", "Backspace": "⌫ Bksp", "Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "L Win": "◆", "R Win": "◆", "App": "☰", "Scroll Lock": "Scroll Lk", "Pause": "Pause", "PrtSc":"PrtSc", "Insert":"Ins", "Home":"Home", "Page Up":"PgUp", "Delete":"Del", "End":"End", "Page Down":"PgDn", "L Ctrl":"Ctrl", "R Ctrl":"Ctrl", "L Alt":"Alt", "R Alt":"AltGr", "Space":"Space", "Esc":"Esc", "About":"About", "Set":"Set", "LShift": "⇧ Shift", "RShift": "⇧ Shift", "Minimize":"_", "Close":"X", "Donate":"Donate"}

        active_layout_code = self.current_language
        active_layout_map = self.loaded_layouts.get(active_layout_code)
        fallback_map = self.loaded_layouts.get('us', self.loaded_layouts.get('en', FALLBACK_CHAR_MAP if isinstance(FALLBACK_CHAR_MAP, dict) else {} ))
        if active_layout_map is None:
            # print(f"Warning: Layout '{active_layout_code}' not loaded. Using fallback.")
            active_layout_map = fallback_map

        for key_name, button in self.buttons.items():
            if not button: continue
            new_label = key_name
            toggled = False
            is_mod_visual = key_name in ['LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock']

            if key_name == 'Lang':
                available_layouts = self.xkb_manager.get_available_layouts() if self.xkb_manager else list(self.loaded_layouts.keys())
                if not available_layouts: available_layouts = ['us']
                current_index = -1
                try: current_index = available_layouts.index(self.current_language)
                except ValueError: pass
                next_index = (current_index + 1) % len(available_layouts) if len(available_layouts) > 0 else 0
                next_lang_code = available_layouts[next_index] if len(available_layouts) > 0 else '??'
                new_label = next_lang_code.upper()

            elif key_name in ['LShift', 'RShift']: new_label="⇧ Shift"; toggled=self.shift_pressed
            elif key_name in ['L Ctrl', 'R Ctrl']: new_label="Ctrl"; toggled=self.ctrl_pressed
            elif key_name in ['L Alt', 'R Alt']: new_label="Alt" if key_name=='L Alt' else "AltGr"; toggled=self.alt_pressed
            elif key_name in ['L Win', 'R Win']: new_label="◆"
            elif key_name == 'Caps Lock': new_label=symbol_map.get(key_name, key_name); toggled=self.caps_lock_pressed
            elif key_name == 'App': new_label="☰"
            elif key_name in X11_KEYSYM_MAP:
                char_tuple = active_layout_map.get(key_name, fallback_map.get(key_name))

                if char_tuple and isinstance(char_tuple, (list, tuple)) and len(char_tuple) >= 1:
                    index_to_use = 0
                    is_letter = key_name.isalpha() and len(key_name)==1
                    should_be_shifted = (self.shift_pressed ^ self.caps_lock_pressed) if is_letter else self.shift_pressed
                    if should_be_shifted and len(char_tuple) > 1 and char_tuple[1] is not None:
                        index_to_use = 1
                    new_label = char_tuple[index_to_use] if index_to_use < len(char_tuple) else char_tuple[0]
                    if should_be_shifted and len(char_tuple) > 1 and char_tuple[1] is None:
                        new_label = char_tuple[0]
                elif key_name in symbol_map:
                     new_label = symbol_map[key_name]
            elif key_name in symbol_map: new_label = symbol_map[key_name]
            elif key_name.startswith("F") and key_name[1:].isdigit(): new_label = key_name

            if button.text() != new_label: button.setText(new_label)

            if is_mod_visual:
                current_prop = button.property("modifier_on");
                if current_prop is None or current_prop != toggled:
                    button.setProperty("modifier_on", toggled);
                    button.style().unpolish(button); button.style().polish(button)
            else:
                current_prop = button.property("modifier_on")
                if current_prop is not None and current_prop is True:
                     button.setProperty("modifier_on", False)
                     button.style().unpolish(button); button.style().polish(button)


    def _simulate_single_key_press(self, key_name):
        if not key_name: return False
        is_letter = key_name.isalpha() and len(key_name)==1
        if key_name in ['Up', 'Down', 'Left', 'Right']:
             effective_shift = self.shift_pressed
        else:
             effective_shift = (self.shift_pressed ^ self.caps_lock_pressed) if is_letter else self.shift_pressed
        sim_ok = self._send_xtest_key(key_name, effective_shift)
        return sim_ok

    def _send_xtest_key(self, key_name, simulate_shift, is_caps_toggle=False):
        """ Sends the low-level XTEST key event sequence. """
        caps_kc = xlib_int.get_caps_lock_keycode(); shift_kc = xlib_int.get_shift_keycode(); ctrl_kc = xlib_int.get_ctrl_keycode(); alt_kc = xlib_int.get_alt_keycode()

        if is_caps_toggle:
             if not self.xlib_ok or not caps_kc: print("XTEST Error: Cannot toggle Caps Lock"); return False
             ok = xlib_int.send_xtest_event(X_CONST.KeyPress, caps_kc) and xlib_int.send_xtest_event(X_CONST.KeyRelease, caps_kc)
             if not ok: self._handle_xtest_error(); return False
             return True
        if not self.xlib_ok: return False
        keysym = X11_KEYSYM_MAP.get(key_name);
        if keysym is None or keysym == 0: print(f"No/Invalid X11 KeySym for '{key_name}'"); return False
        kc = xlib_int.keysym_to_keycode(keysym);
        if not kc: print(f"WARNING: No KeyCode for KeySym {hex(keysym)} ('{key_name}')"); return False
        press_shift = simulate_shift and shift_kc; press_ctrl = self.ctrl_pressed and ctrl_kc; press_alt = self.alt_pressed and alt_kc
        ok = True
        try:
            if press_ctrl: ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, ctrl_kc)
            if press_alt: ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, alt_kc)
            if press_shift: ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, shift_kc)
            if not ok: raise Exception("Mod Press")

            ok &= xlib_int.send_xtest_event(X_CONST.KeyPress, kc); ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, kc)
            if not ok: raise Exception("Key Press/Release")

            if press_shift: ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, shift_kc)
            if press_alt: ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, alt_kc)
            if press_ctrl: ok &= xlib_int.send_xtest_event(X_CONST.KeyRelease, ctrl_kc)
            if not ok: raise Exception("Mod Release")
            return True
        except Exception as e:
            print(f"ERROR XTEST sequence '{key_name}': {e}"); self._handle_xtest_error()
            try:
                if press_shift: xlib_int.send_xtest_event(X_CONST.KeyRelease, shift_kc)
                if press_alt: xlib_int.send_xtest_event(X_CONST.KeyRelease, alt_kc)
                if press_ctrl: xlib_int.send_xtest_event(X_CONST.KeyRelease, ctrl_kc)
            except Exception: pass
            return False

    def _handle_xtest_error(self, critical=False):
        if self.xlib_ok:
            self.xlib_ok = False; print("XTEST disabled."); xlib_int.flush_display()
            msg = "X connection lost?" if critical else "Key simulation error."
            QMessageBox.warning(self, "XTEST Error", f"{msg}\nXTEST disabled."); self.init_tray_icon()

    def on_modifier_key_press(self, key_name):
        """ Handles clicks on modifier keys (Shift, Ctrl, Alt, Caps). """
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        mod_changed = False
        if key_name in ['LShift', 'RShift']: self.shift_pressed = not self.shift_pressed; mod_changed=True
        elif key_name in ['L Ctrl', 'R Ctrl']: self.ctrl_pressed = not self.ctrl_pressed; mod_changed=True
        elif key_name in ['L Alt', 'R Alt']: self.alt_pressed = not self.alt_pressed; mod_changed=True
        elif key_name == 'Caps Lock':
            sim_success = self._send_xtest_key(key_name, False, is_caps_toggle=True)
            if sim_success: self.caps_lock_pressed = not self.caps_lock_pressed
            else: QMessageBox.warning(self, "Caps Lock Error", "Could not toggle sys Caps Lock.")
            mod_changed = True
        if mod_changed: self.update_key_labels()

    def on_non_repeatable_key_press(self, key_name):
        """ Handles clicks on non-repeatable keys like Esc, F-keys, Win, App. """
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        sim_ok = self._send_xtest_key(key_name, False)
        released_mods = False
        if sim_ok:
            if self.ctrl_pressed: self.ctrl_pressed = False; released_mods = True
            if self.alt_pressed: self.alt_pressed = False; released_mods = True
        if released_mods: self.update_key_labels()

    def _handle_key_pressed(self, key_name):
        """ Handles the initial press of a potentially repeating key. """
        if self.repeating_key_name and self.repeating_key_name != key_name:
            self._handle_key_released(self.repeating_key_name, force_stop=True)

        should_release_mods = key_name in FALLBACK_CHAR_MAP or key_name == 'Space'
        if key_name in ['Backspace', 'Delete', 'Tab', 'Enter', 'Up', 'Down', 'Left', 'Right']:
             should_release_mods = False

        sim_ok = self._simulate_single_key_press(key_name)
        released_mods = False
        if sim_ok and should_release_mods:
            if self.shift_pressed: self.shift_pressed = False; released_mods = True
            if self.ctrl_pressed: self.ctrl_pressed = False; released_mods = True
            if self.alt_pressed: self.alt_pressed = False; released_mods = True

        if released_mods:
             self.update_key_labels()

        if sim_ok and self.settings.get("auto_repeat_enabled", DEFAULT_SETTINGS.get("auto_repeat_enabled", True)):
            self.repeating_key_name = key_name
            self.initial_delay_timer.start()

    def _handle_key_released(self, key_name, force_stop=False):
        """ Handles the release of a potentially repeating key. """
        if force_stop or (self.repeating_key_name == key_name):
            if self.repeating_key_name:
                self.initial_delay_timer.stop()
                self.auto_repeat_timer.stop()
                self.repeating_key_name = None

    def _trigger_initial_repeat(self):
        """ Called after the initial delay. Starts the actual repeat timer. """
        if self.repeating_key_name:
            sim_ok = self._simulate_single_key_press(self.repeating_key_name)
            if sim_ok:
                self.auto_repeat_timer.start()
            else:
                self._handle_key_released(self.repeating_key_name, force_stop=True)
        else:
            self.initial_delay_timer.stop()
            self.auto_repeat_timer.stop()

    def _trigger_subsequent_repeat(self):
        """ Called by the auto_repeat_timer for each repeat action. """
        if self.repeating_key_name:
            sim_ok = self._simulate_single_key_press(self.repeating_key_name)
            if not sim_ok:
                self._handle_key_released(self.repeating_key_name, force_stop=True)
        else:
            self.auto_repeat_timer.stop()

    def on_typable_key_right_press(self, key_name):
        """ Handles right-click on typable keys: Simulates Shift + Key. """
        print(f"Right-click detected on typable key: {key_name}")
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        sim_ok = self._send_xtest_key(key_name, True) # Simulate shift = True
        released_mods = False
        if sim_ok:
            if self.ctrl_pressed: self.ctrl_pressed = False; released_mods = True
            if self.alt_pressed: self.alt_pressed = False; released_mods = True
        if released_mods: self.update_key_labels()


# file:virtual_keyboard_gui.py
