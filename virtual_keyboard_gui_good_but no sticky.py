# -*- coding: utf-8 -*-
# Contains the main VirtualKeyboard class, UI, event handling, and integration logic.

import sys
import os
from typing import Optional, Tuple
import re
import copy
import webbrowser
from pathlib import Path # Required for file URI in About dialog

try:
    # Import necessary PyQt6 modules
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QPushButton, QGridLayout, QSizePolicy,
        QSystemTrayIcon, QMenu, QMessageBox
    )
    from PyQt6.QtCore import Qt, QSize, QEvent, QPoint, QTimer, pyqtSignal, QRect
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
from .key_definitions import KEYBOARD_LAYOUT, KEY_CHAR_MAP, X11_KEYSYM_MAP
from . import xlib_integration as xlib_int
# --- تمت الإضافة: استيراد Xlib و X اذا لم يكن dummy ---
if not xlib_int.is_dummy():
    import Xlib # Import the real Xlib
    from Xlib import X # Import X constants
else:
    Xlib = None # Define as None if dummy is used
# --- نهاية الإضافة ---

from .xlib_integration import X as X_CONST # Use alias for X KeyPress/Release constants
from .XKB_Switcher import XKBManager, XKBManagerError

# --- Optional Focus Monitor Import (Relative Import) ---
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

# --- Constants for defining resize edges ---
EDGE_NONE = 0; EDGE_TOP = 1; EDGE_BOTTOM = 2; EDGE_LEFT = 4; EDGE_RIGHT = 8
EDGE_TOP_LEFT = EDGE_TOP | EDGE_LEFT; EDGE_TOP_RIGHT = EDGE_TOP | EDGE_RIGHT
EDGE_BOTTOM_LEFT = EDGE_BOTTOM | EDGE_LEFT; EDGE_BOTTOM_RIGHT = EDGE_BOTTOM | EDGE_RIGHT


# --- Main Application Window ---
class VirtualKeyboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python XKeyboard")
        self.settings = load_settings() # Load settings first

        # --- تحميل الإعدادات المتعلقة بالنافذة ---
        self.is_frameless = self.settings.get("frameless_window", DEFAULT_SETTINGS.get("frameless_window", False))
        self.always_on_top = self.settings.get("always_on_top", DEFAULT_SETTINGS.get("always_on_top", True))
        self.is_sticky = self.settings.get("sticky_on_all_workspaces", DEFAULT_SETTINGS.get("sticky_on_all_workspaces", False)) # تحميل حالة الالتصاق
        # --- نهاية تحميل الإعدادات ---

        self.app_font = QFont()
        self.load_initial_font_settings()
        xlib_int.initialize_xlib(); self.xlib_ok = xlib_int.is_xtest_ok(); self.is_xlib_dummy = xlib_int.is_dummy()

        # --- إعداد علامات النافذة بناءً على الإعدادات ---
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        base_flags = Qt.WindowType.Window
        base_flags |= Qt.WindowType.WindowDoesNotAcceptFocus # دائما لا تقبل التركيز

        if self.always_on_top:
            base_flags |= Qt.WindowType.WindowStaysOnTopHint
            print("Window initialized with Always on Top hint.")
        else:
            print("Window initialized without Always on Top hint.")

        if self.is_frameless:
            base_flags |= Qt.WindowType.FramelessWindowHint
            print("Window initialized as frameless.")
        else:
            # Framed window gets standard buttons
            base_flags |= (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)
            print("Window initialized with standard frame.")
        self.setWindowFlags(base_flags)
        # --- نهاية إعداد العلامات ---


        self.resizing = False; self.resize_edge = EDGE_NONE; self.resize_start_pos = None; self.resize_start_geom = None
        self.resize_margin = 4
        self.setMouseTracking(True)
        self.buttons = {}; self.current_language = 'en'; self.shift_pressed = False; self.ctrl_pressed = False; self.alt_pressed = False; self.caps_lock_pressed = False
        self.drag_position = None; self.xkb_manager = None; self.tray_icon = None; self.icon = None; self.language_menu = None; self.language_actions = {}; self.lang_action_group = None
        self.focus_monitor = None; self.focus_monitor_available = _focus_monitor_available
        self.tray_menu = None
        self.monitor_was_running_for_context_menu = False

        # --- تحميل الأيقونة من الملفات ---
        self.icon = self.load_app_icon()

        # Auto-Repeat Variables and Timers
        self.repeating_key_name = None
        self.initial_delay_timer = QTimer(self)
        self.initial_delay_timer.setSingleShot(True)
        self.initial_delay_timer.timeout.connect(self._trigger_initial_repeat)
        self.auto_repeat_timer = QTimer(self)
        self.auto_repeat_timer.timeout.connect(self._trigger_subsequent_repeat)
        self._update_repeat_timers_from_settings()

        self.init_xkb_manager()
        self.central_widget = QWidget(); self.central_widget.setObjectName("centralWidget"); self.central_widget.setMouseTracking(True); self.central_widget.setAutoFillBackground(True)
        self.setCentralWidget(self.central_widget); self.grid_layout = QGridLayout(self.central_widget); self.grid_layout.setSpacing(3); self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.init_focus_monitor()
        self._apply_global_styles_and_font() # Apply styles *after* setting flags and central widget
        self.init_ui()

        # --- تعيين الأيقونة للنافذة وشريط النظام ---
        if self.icon:
            self.setWindowIcon(self.icon) # تعيين أيقونة النافذة
        self.init_tray_icon(); # استدعاء لإنشاء/تحديث أيقونة شريط النظام (سيستخدم self.icon)
        # --- نهاية التعيين ---

        self.apply_initial_geometry()
        self.layout_check_timer = QTimer(self); self.layout_check_timer.timeout.connect(self.check_system_layout);
        if self.xkb_manager: self.layout_check_timer.start(1000)

        # --- تطبيق حالة الالتصاق الأولية بعد إنشاء النافذة ومعرفها ---
        # استخدام مؤقت قصير للتأكد من أن النافذة معروفة لمدير النوافذ
        QTimer.singleShot(100, lambda: self._set_sticky_state(self.is_sticky))
        # -----------------------------------------------------------

    # --- دالة تحميل الأيقونة من الملفات ---
    def load_app_icon(self) -> Optional[QIcon]:
        """ Loads the application icon from predefined PNG files. """
        icon = QIcon()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(script_dir, 'icons')
        icon_files = [
            os.path.join(icon_dir, "icon_32.png"),
            os.path.join(icon_dir, "icon_64.png"),
            os.path.join(icon_dir, "icon_128.png"),
            os.path.join(icon_dir, "icon_256.png"),
        ]

        found_any = False
        for file_path in icon_files:
            if os.path.exists(file_path):
                 icon.addFile(file_path)
                 # print(f"Icon loader: Added '{os.path.basename(file_path)}'") # Less verbose
                 found_any = True
            else:
                 print(f"Icon loader: File not found '{os.path.basename(file_path)}'")

        if found_any:
            print("Icon loaded successfully from files.")
            return icon
        else:
            print("No icon files found. Generating default icon.")
            return self.generate_keyboard_icon()
    # --- نهاية دالة تحميل الأيقونة ---

    # --- الدالة البديلة لتوليد أيقونة ---
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
    # --- نهاية الدالة البديلة ---

    def _update_repeat_timers_from_settings(self):
        delay_ms = self.settings.get("auto_repeat_delay_ms", DEFAULT_SETTINGS.get("auto_repeat_delay_ms", 1500))
        interval_ms = self.settings.get("auto_repeat_interval_ms", DEFAULT_SETTINGS.get("auto_repeat_interval_ms", 100))
        self.initial_delay_timer.setInterval(delay_ms)
        self.auto_repeat_timer.setInterval(interval_ms)
        # print(f"Auto-repeat timers updated: Delay={delay_ms}ms, Interval={interval_ms}ms") # Less verbose

    def load_initial_font_settings(self):
        font_family = self.settings.get("font_family", DEFAULT_SETTINGS.get("font_family", "Sans Serif"));
        font_size = self.settings.get("font_size", DEFAULT_SETTINGS.get("font_size", 9))
        try:
            self.app_font.setFamily(font_family); self.app_font.setPointSize(font_size); print(f"Loaded font: {self.app_font.family()} {self.app_font.pointSize()}pt")
            # Do not save back here, let save_settings handle consistency
            # self.settings["font_family"] = self.app_font.family(); self.settings["font_size"] = self.app_font.pointSize()
        except Exception as e:
            print(f"ERROR creating font: {e}. Using default."); self.app_font.setFamily(DEFAULT_SETTINGS.get("font_family", "Sans Serif")); self.app_font.setPointSize(DEFAULT_SETTINGS.get("font_size", 9))
            # Do not save back here
            # self.settings["font_family"] = self.app_font.family(); self.settings["font_size"] = self.app_font.pointSize()

    def apply_initial_geometry(self):
        initial_geom_applied = False; min_width, min_height = 400, 130
        if self.settings.get("remember_geometry", DEFAULT_SETTINGS.get("remember_geometry", True)):
            geom = self.settings.get("window_geometry") # Don't need default here, None is fine
            if geom and isinstance(geom, dict) and all(k in geom for k in ["x", "y", "width", "height"]):
                try:
                    width = max(min_width, geom["width"]); height = max(min_height, geom["height"]); print(f"Applying saved geometry: x={geom['x']}, y={geom['y']}, w={width}, h={height}")
                    self.setGeometry(geom["x"], geom["y"], width, height); initial_geom_applied = True
                except Exception as e: print(f"ERROR applying saved geometry: {e}."); self.settings["window_geometry"] = None
        if not initial_geom_applied: print("Applying default geometry."); self.resize(900, 180); self.center_window()
        self.setMinimumSize(min_width, min_height)

    def init_xkb_manager(self):
        if XKBManager:
            try:
                self.xkb_manager = XKBManager(auto_refresh=False)
                if self.xkb_manager.refresh():
                     initial_layout = self.xkb_manager.query_current_layout_name()
                     if initial_layout: self.xkb_manager.set_layout_by_name(initial_layout, update_system=False)
                     print(f"XKBManager Initialized: SUCCESS (Layouts: {self.xkb_manager.get_available_layouts()})")
                else: print("XKBManager Initialized: ERROR - Initial refresh failed."); self.xkb_manager = None
            except (XKBManagerError, Exception) as e: print(f"XKBManager Initialized: ERROR - {e}"); self.xkb_manager = None
        else: print("XKBManager Initialized: Module not found."); self.current_language = 'en'

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
        if not self.central_widget: return
        text_color = self.settings.get("text_color", DEFAULT_SETTINGS.get("text_color", "#000000"))
        button_style_name = self.settings.get("button_style", DEFAULT_SETTINGS.get("button_style", "default"))
        opacity_level = self.settings.get("window_opacity", DEFAULT_SETTINGS.get("window_opacity", 1.0))
        font_family = self.app_font.family(); font_size = self.app_font.pointSize()

        base_button_style_parts = [f"color: {text_color};", f"font-family: '{font_family}';", f"font-size: {font_size}pt;", "padding: 2px;"]
        if button_style_name == "flat": base_button_style_parts.extend(["border: 1px solid #aaaaaa;","background-color: #e8e8e8;","border-radius: 3px;"])
        elif button_style_name == "gradient": base_button_style_parts.extend(["border: 1px solid #bbbbbb;","""background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #fefefe, stop: 1 #e0e0e0);""","border-radius: 4px;"])

        base_button_style = " ".join(base_button_style_parts); toggled_modifier_style = "background-color: #a0cfeC; border: 1px solid #0000A0; font-weight: bold;"
        custom_control_style = "font-weight: bold; font-size: 10pt;"; donate_style = "font-size: 10pt; font-weight: bold; color: #81812D;"

        # Apply background style based on frameless status
        alpha_value = int(max(0.0, min(1.0, opacity_level)) * 255)
        palette = self.palette()
        base_color = palette.color(QPalette.ColorRole.Window) # Get theme window color
        background_rgba = f"rgba({base_color.red()}, {base_color.green()}, {base_color.blue()}, {alpha_value})"
        # Only apply translucent background if frameless
        bg_style = f"background-color: {background_rgba};" if self.is_frameless else ""
        self.central_widget.setStyleSheet(f"QWidget#centralWidget {{ {bg_style} }}")

        # Apply button styles
        full_stylesheet = f"""
            QPushButton {{ {base_button_style} }}
            QPushButton:pressed {{ background-color: #cceeff; border: 1px solid #88aabb; }}
            QPushButton[modifier_on="true"] {{ {toggled_modifier_style} }}
            QPushButton#MinimizeButton, QPushButton#CloseButton {{ {custom_control_style} }}
            QPushButton#DonateButton {{ {donate_style} }}
        """
        self.setStyleSheet(full_stylesheet) # Apply to the main window

    def update_application_font(self, new_font): self.app_font = QFont(new_font)
    def update_application_opacity(self, opacity_level): self.settings["window_opacity"] = max(0.0, min(1.0, opacity_level))
    def update_application_text_color(self, color_str):
        if not (isinstance(color_str, str) and color_str.startswith('#') and (len(color_str) == 7 or len(color_str) == 9)): color_str = DEFAULT_SETTINGS.get("text_color", "#000000")
        self.settings["text_color"] = color_str
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
        for r, row_keys in enumerate(KEYBOARD_LAYOUT):
            col = 0
            for key_data in row_keys:
                if key_data:
                    key_name, row_span, col_span = key_data
                    initial_label = symbol_map.get(key_name, key_name)
                    if key_name.startswith("F") and key_name[1:].isdigit(): initial_label = key_name
                    elif key_name == "Lang": initial_label = "Lang"

                    button_class = QPushButton
                    button = button_class(initial_label)
                    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    button.setAutoRepeat(False) # We handle our own repeat

                    if key_name == 'Minimize': button.setObjectName("MinimizeButton")
                    if key_name == 'Close': button.setObjectName("CloseButton")
                    if key_name == 'Donate': button.setObjectName("DonateButton")

                    is_modifier_key = key_name in ['LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock']
                    is_custom_control_key = key_name in ['Minimize', 'Close']
                    is_typable_key = key_name in KEY_CHAR_MAP or key_name in ['Space', 'Backspace', 'Delete', 'Tab', 'Enter']

                    if is_modifier_key: button.setProperty("modifier_on", False)

                    if key_name in ['About', 'Set', 'Minimize', 'Close', 'Donate', 'Lang']:
                        if key_name == 'Lang': button.clicked.connect(self.toggle_language)
                        elif key_name == 'About': button.clicked.connect(self.show_about_message)
                        elif key_name == 'Set': button.clicked.connect(self.open_settings_dialog)
                        elif key_name == 'Minimize': button.clicked.connect(self.hide_to_tray)
                        elif key_name == 'Close': button.clicked.connect(self.quit_application)
                        elif key_name == 'Donate': button.clicked.connect(self._open_donate_link)
                    elif is_modifier_key:
                        button.clicked.connect(lambda chk=False, k=key_name: self.on_modifier_key_press(k))
                    elif is_typable_key:
                        button.pressed.connect(lambda k=key_name: self._handle_key_pressed(k))
                        button.released.connect(lambda k=key_name: self._handle_key_released(k))
                        button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                        button.customContextMenuRequested.connect(lambda pos, k=key_name: self.on_typable_key_right_press(k))
                    else: # Other functional keys (F-keys, nav keys etc.)
                        button.clicked.connect(lambda chk=False, k=key_name: self.on_non_repeatable_key_press(k))

                    self.grid_layout.addWidget(button, r, col, row_span, col_span)
                    self.buttons[key_name] = button
                    # إظهار/إخفاء الأزرار المخصصة بناءً على حالة الإطار
                    if is_custom_control_key:
                         button.setVisible(self.is_frameless)
                    col += col_span
                else: col += 1
        if self.xkb_manager: self.sync_vk_lang_with_system(initial_setup=True)
        else: self.update_key_labels()

    def _open_donate_link(self):
        url = "https://paypal.me/kh1512"; print(f"Opening donation link: {url}")
        try: webbrowser.open_new_tab(url)
        except Exception as e: print(f"ERROR opening donation link: {e}"); QMessageBox.warning(self, "Link Error", f"Could not open donation link:\n{url}\n\nError: {e}")

    def hide_to_tray(self):
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            try:
                 self.tray_icon.showMessage(self.windowTitle(), "Minimized to system tray.", self.icon if self.icon else QIcon(), 2000)
            except Exception as e:
                 print(f"Tray message failed: {e}")
        elif not self.is_frameless:
            # نافذة بإطار بدون شريط مهام: قم بالتصغير العادي
            print("No tray, minimizing.")
            self.showMinimized()
        else:
            # نافذة بدون إطار وبدون شريط مهام: قم بالإخفاء
            print("No tray and frameless, hiding window.")
            self.hide()

    def init_tray_icon(self):
        """ Initializes or updates the system tray icon and its context menu. """
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
            # Update existing icon if needed
            if self.icon and self.tray_icon.icon().cacheKey() != self.icon.cacheKey():
                 try: print("Updating tray icon..."); self.tray_icon.setIcon(self.icon)
                 except Exception as e: print(f"Tray icon update error: {e}")

        # --- إعادة بناء القائمة دائمًا للتأكد من صحتها ---
        if self.tray_menu: self.tray_menu.clear() # Clear previous menu items
        self.tray_menu = QMenu(self); self.language_menu = None; self.language_actions = {}; self.lang_action_group = None

        if self.xkb_manager:
            layouts = self.xkb_manager.get_available_layouts()
            if layouts and len(layouts) > 1: # Only show layout menu if more than one
                self.language_menu = QMenu("Select Layout", self); self.lang_action_group = QActionGroup(self); self.lang_action_group.setExclusive(True)
                for lc in layouts: a = QAction(lc, self, checkable=True); a.triggered.connect(lambda checked=False, l=lc: self.set_system_language_from_menu(l)); self.language_menu.addAction(a); self.language_actions[lc] = a; self.lang_action_group.addAction(a)
                self.tray_menu.addMenu(self.language_menu); self.tray_menu.addSeparator()

        about_action = QAction("About...", self); about_action.triggered.connect(self.show_about_message)
        settings_action = QAction("Settings...", self); settings_action.triggered.connect(self.open_settings_dialog)
        self.tray_menu.addActions([about_action, settings_action])

        # --- إضافة خيار التبرع ---
        donate_action = QAction("Donate...", self)
        donate_action.triggered.connect(self._open_donate_link)
        self.tray_menu.addAction(donate_action)
        # --- نهاية الإضافة ---

        self.tray_menu.addSeparator()

        show_act = QAction("Show Keyboard", self); show_act.triggered.connect(self.show_normal_and_raise)
        hide_act = QAction("Hide (Middle Mouse Click)", self); hide_act.setEnabled(self.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True))); hide_act.triggered.connect(self.hide_to_tray)
        self.tray_menu.addActions([show_act, hide_act]); self.tray_menu.addSeparator()

        quit_act = QAction("Quit", self); quit_act.triggered.connect(self.quit_application)
        self.tray_menu.addAction(quit_act); self.tray_icon.setContextMenu(self.tray_menu)
        # --- نهاية إعادة بناء القائمة ---

        if not self.tray_icon.isVisible():
             try: self.tray_icon.show()
             except Exception as e: print(f"Tray show error: {e}")

        tooltip_parts = [self.windowTitle()]
        if self.xkb_manager: tooltip_parts.append(f"Layout: {self.xkb_manager.get_current_layout_name() or 'N/A'}")
        if not self.xlib_ok: tooltip_parts.append("Input ERR")
        if self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False)): tooltip_parts.append("AutoShow ON")
        if self.always_on_top: tooltip_parts.append("Always On Top")
        if self.is_sticky: tooltip_parts.append("Sticky") # إضافة حالة الالتصاق للتلميح
        try: self.tray_icon.setToolTip("\n".join(tooltip_parts))
        except Exception as e: print(f"Tray tooltip error: {e}")
        self.update_tray_menu_check_state()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger: self.show_normal_and_raise()

    def show_normal_and_activate(self):
        if self.isHidden(): self.showNormal(); self.activateWindow(); self.raise_()

    def closeEvent(self, event):
        # --- تعديل: إخفاء إلى شريط المهام عند الإغلاق فقط إذا كان شريط المهام متاحًا ---
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide_to_tray()
        else:
            # إذا لم يكن شريط المهام متاحًا، قم بإنهاء التطبيق عند الإغلاق
            event.accept() # Accept the event to close
            self.quit_application() # Ensure cleanup happens

    def quit_application(self):
        print("Quit requested...")
        if hasattr(self, 'layout_check_timer'): self.layout_check_timer.stop()
        self.initial_delay_timer.stop()
        self.auto_repeat_timer.stop()
        if self.focus_monitor and self.focus_monitor.is_running():
            try: self.focus_monitor.stop()
            except Exception as e: print(f"Error stopping focus monitor: {e}")
        if self.settings.get("remember_geometry", DEFAULT_SETTINGS.get("remember_geometry", True)):
            try:
                # حفظ الهندسة فقط إذا لم تكن النافذة مصغرة
                if not self.isMinimized(): # isMaximized is less relevant for this type of tool
                     self.settings["window_geometry"] = {"x": self.geometry().x(),"y": self.geometry().y(),"width": self.geometry().width(),"height": self.geometry().height()}
                # else: keep the previously saved geometry if minimized
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
            if XKBManager is None: status_xkb = "Disabled (XKB_Switcher missing)"
            elif self.xkb_manager: status_xkb = f"Enabled (Layouts: {', '.join(self.xkb_manager.get_available_layouts() or ['N/A'])})"
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
                    # print(f"Using badge URI: {badge_uri}") # Less verbose
                except Exception as uri_e:
                     print(f"Error creating file URI for badge: {uri_e}")
                     badge_html = f'<img src="{badge_icon_path_relative}" alt="Icon" width="64" height="64" style="float: left; margin-right: 10px; margin-bottom: 10px;">'
            else:
                print(f"Badge icon not found: {badge_icon_path_full}")

            main_info = f"""
             {badge_html}
             <div style="overflow: hidden;">
             <p><b>{program_name} v1.0.1</b><br>A simple on-screen virtual keyboard.</p>
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
            self.init_tray_icon() # Refresh tray icon status

    def open_settings_dialog(self):
        settings_copy = copy.deepcopy(self.settings); dialog = SettingsDialog(settings_copy, self.app_font, self.focus_monitor_available, self)
        # Connect the signal BEFORE showing the dialog
        dialog.settingsApplied.connect(self._apply_settings_from_dialog)
        monitor_was_running = False
        if self.focus_monitor and self.focus_monitor.is_running():
            print("Pausing focus monitor for Settings dialog...");
            try: self.focus_monitor.stop(); monitor_was_running = True
            except Exception as e: print(f"ERROR stopping focus monitor: {e}")
        try:
            dialog.exec() # Show the dialog modally
        finally:
            # Resume monitor logic (runs after dialog is closed, regardless of OK/Cancel)
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

            # Refresh tray (might need updated tooltip based on settings)
            self.init_tray_icon()

            # Disconnect signal AFTER the dialog is closed and settings (potentially) applied
            try: dialog.settingsApplied.disconnect(self._apply_settings_from_dialog)
            except (TypeError, RuntimeError): pass # Ignore if already disconnected or failed

    # --- تمت الإضافة: دالة لتغيير حالة الالتصاق ---
    def _set_sticky_state(self, sticky: bool):
        """Sets the window's sticky state using Xlib EWMH hints."""
        if self.is_xlib_dummy or not Xlib:
            print("Sticky state: Skipped (Xlib dummy or not imported)")
            return
        display = xlib_int.get_display()
        if not display:
            print("Sticky state: Skipped (No X display)")
            return

        try:
            win_id = self.winId()
            if not win_id:
                 print("Sticky state: Failed (Invalid winId)")
                 return

            NET_WM_STATE = display.intern_atom('_NET_WM_STATE')
            NET_WM_STATE_STICKY = display.intern_atom('_NET_WM_STATE_STICKY')

            if not NET_WM_STATE or not NET_WM_STATE_STICKY:
                print("Sticky state: Failed (Could not get EWMH atoms. WM incompatible?)")
                return

            action = 1 if sticky else 0  # 1 = add state, 0 = remove state
            # Format: action, atom1, atom2, source indication (1=app), 0
            data = (action, NET_WM_STATE_STICKY, 0, 1, 0)

            root = display.screen().root
            event = Xlib.protocol.event.ClientMessage(
                window=win_id,
                client_type=NET_WM_STATE,
                data=(32, data) # 32-bit format
            )

            # Send event to the root window
            mask = (X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            root.send_event(event, event_mask=mask)
            display.flush()
            print(f"Sticky state: {'Enabled' if sticky else 'Disabled'} (EWMH message sent)")

        except Exception as e:
            print(f"Sticky state: ERROR applying - {e}", file=sys.stderr)
            # Optionally try flushing display again on error
            try:
                if display: display.flush()
            except: pass
    # --- نهاية الإضافة ---


    def _apply_settings_from_dialog(self, applied_settings):
        """Applies settings received from the settings dialog."""
        print("Applying settings from dialog...");
        previous_frameless = self.is_frameless
        previous_on_top = self.always_on_top
        previous_sticky = self.is_sticky # حفظ الحالة السابقة للالتصاق

        # Update the main settings dictionary *first*
        self.settings = copy.deepcopy(applied_settings)

        # Update internal state variables based on new settings
        self.is_frameless = self.settings.get("frameless_window", DEFAULT_SETTINGS.get("frameless_window", False))
        self.always_on_top = self.settings.get("always_on_top", DEFAULT_SETTINGS.get("always_on_top", True))
        self.is_sticky = self.settings.get("sticky_on_all_workspaces", DEFAULT_SETTINGS.get("sticky_on_all_workspaces", False)) # تحديث حالة الالتصاق

        # Apply visual settings that don't require window recreation
        new_font = QFont(self.settings.get("font_family", DEFAULT_SETTINGS.get("font_family", "Sans Serif")),
                         self.settings.get("font_size", DEFAULT_SETTINGS.get("font_size", 9)))
        if new_font != self.app_font:
            self.update_application_font(new_font)

        self.update_application_opacity(self.settings.get("window_opacity", DEFAULT_SETTINGS.get("window_opacity", 1.0)))
        self.update_application_text_color(self.settings.get("text_color", DEFAULT_SETTINGS.get("text_color", "#000000")))
        self.update_application_button_style(self.settings.get("button_style", DEFAULT_SETTINGS.get("button_style", "default")))
        self._update_repeat_timers_from_settings()

        # Check if window flags need changing
        flags_changed = (self.is_frameless != previous_frameless or self.always_on_top != previous_on_top)

        if flags_changed:
            print("Window flags changed, re-applying...")
            # Construct the new flags
            base_flags = Qt.WindowType.Window
            base_flags |= Qt.WindowType.WindowDoesNotAcceptFocus

            if self.always_on_top:
                base_flags |= Qt.WindowType.WindowStaysOnTopHint
            if self.is_frameless:
                base_flags |= Qt.WindowType.FramelessWindowHint
            else:
                # Framed window gets standard buttons
                base_flags |= (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)

            # Important: Hide/Show to ensure WM picks up flag changes reliably
            current_visibility = self.isVisible()
            print("  Hiding window to apply flags...")
            self.hide()
            print(f"  Setting flags: {base_flags}")
            self.setWindowFlags(base_flags)
            print("  Flags set.")
            # Reapply styles *after* setting flags but *before* showing
            self._apply_global_styles_and_font()
            # Re-initialize UI elements dependent on frameless state
            for key_name in ['Minimize', 'Close']:
                 if key_name in self.buttons:
                      self.buttons[key_name].setVisible(self.is_frameless)
            print("Custom button visibility updated.")

            if current_visibility:
                print("  Re-showing window...")
                # Use a small delay before showing to allow WM to process flags
                QTimer.singleShot(50, self.show)
            else:
                 print("  Window was hidden, keeping hidden.")
        else:
            # If flags didn't change, just reapply styles and update labels
            self._apply_global_styles_and_font()
            self.update_key_labels()
            print("Styles and labels updated (no flag change).")

        # --- تطبيق حالة الالتصاق إذا تغيرت ---
        if self.is_sticky != previous_sticky:
             print(f"Sticky state changed to: {self.is_sticky}. Applying...")
             self._set_sticky_state(self.is_sticky)
        # --- نهاية تطبيق الالتصاق ---

        # Refresh tray icon (tooltip might change)
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
        if not self.is_frameless: return EDGE_NONE # لا تغيير الحجم إذا كانت النافذة بإطار
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
        # لا تغيير شكل المؤشر إذا كانت النافذة بإطار (تعتمد على إطار النظام)
        if self.is_frameless:
            if edge == EDGE_TOP or edge == EDGE_BOTTOM: cursor_shape = Qt.CursorShape.SizeVerCursor
            elif edge == EDGE_LEFT or edge == EDGE_RIGHT: cursor_shape = Qt.CursorShape.SizeHorCursor
            elif edge == EDGE_TOP_LEFT or edge == EDGE_BOTTOM_RIGHT: cursor_shape = Qt.CursorShape.SizeFDiagCursor
            elif edge == EDGE_TOP_RIGHT or edge == EDGE_BOTTOM_LEFT: cursor_shape = Qt.CursorShape.SizeBDiagCursor

        # تحديث المؤشر فقط إذا تغير
        if self.cursor().shape() != cursor_shape:
            self.setCursor(QCursor(cursor_shape))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            if self.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True)):
                self.hide_to_tray(); event.accept(); return
        elif event.button() == Qt.MouseButton.RightButton:
            # --- إظهار قائمة السياق عند النقر بزر الماوس الأيمن على الخلفية ---
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

            # --- أولاً، تحقق من تغيير الحجم إذا كانت النافذة بدون إطار ---
            if self.is_frameless:
                self.resize_edge = self._get_resize_edge(local_pos)
                if self.resize_edge != EDGE_NONE: # Start resizing if frameless and on edge
                    self.resizing = True; self.resize_start_pos = event.globalPosition().toPoint(); self.resize_start_geom = self.geometry()
                    self._update_cursor_shape(self.resize_edge); print(f"Start resize: {self.resize_edge}"); event.accept(); return

            # --- إذا لم يكن تغيير الحجم، تحقق من بدء السحب (بغض النظر عن الإطار) ---
            target_widget = self.childAt(local_pos)
            # التحقق من أن الضغط على الخلفية (وليس زر)
            is_button = isinstance(target_widget, QPushButton) if target_widget else False
            is_background_click = (target_widget is self.central_widget or target_widget is None or target_widget is self) and not is_button

            if is_background_click:
                # --- بدء السحب بزر الماوس الأيسر على الخلفية دائمًا ---
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft(); print("Start drag (Left Button)"); event.accept(); return

        # --- إذا لم يتم التعامل مع الحدث، اسمح بالانتشار (مثل النقر على الأزرار) ---
        # super().mousePressEvent(event) # قد لا نحتاج استدعاء super إذا قبلنا الحدث

    def mouseMoveEvent(self, event):
        # --- التعامل مع خروج المؤشر من الزر أثناء التكرار (لا تغيير) ---
        if self.repeating_key_name and self.buttons.get(self.repeating_key_name):
             button = self.buttons[self.repeating_key_name]
             if not button.rect().contains(button.mapFromGlobal(event.globalPosition().toPoint())):
                  self._handle_key_released(self.repeating_key_name, force_stop=True)

        # --- التعامل مع تغيير الحجم (لا تغيير، يعمل بزر الماوس الأيسر) ---
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

        # --- التعامل مع السحب (لا تغيير، يعمل بزر الماوس الأيسر) ---
        elif self.drag_position is not None and event.buttons() == Qt.MouseButton.LeftButton:
             new_pos = event.globalPosition().toPoint() - self.drag_position; self.move(new_pos); event.accept(); return

        # --- تحديث شكل المؤشر عند الحواف (فقط إذا كانت النافذة بدون إطار) ---
        elif self.is_frameless and not self.resizing and self.drag_position is None:
             current_edge = self._get_resize_edge(event.position().toPoint()); self._update_cursor_shape(current_edge)

        # --- اسمح بالانتشار إذا لم يتم التعامل مع الحدث ---
        if not (self.is_frameless and (self.resizing or self.drag_position is not None)):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # --- إيقاف التكرار عند تحرير أي زر (لا تغيير) ---
        if self.repeating_key_name:
             self._handle_key_released(self.repeating_key_name, force_stop=True)

        # --- إنهاء تغيير الحجم (لا تغيير، يعمل بزر الماوس الأيسر) ---
        if self.is_frameless and self.resizing and event.button() == Qt.MouseButton.LeftButton:
            self.resizing = False; self.resize_edge = EDGE_NONE; self.resize_start_pos = None; self.resize_start_geom = None; self.unsetCursor(); print("Resize finished"); event.accept(); return

        # --- إنهاء السحب (لا تغيير، يعمل بزر الماوس الأيسر) ---
        elif self.drag_position is not None and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None; print("Drag finished"); event.accept(); return

        # --- إعادة تعيين المؤشر إذا لم يكن هناك أزرار مضغوطة (فقط إذا كانت بدون إطار) ---
        elif self.is_frameless and not self.resizing and not event.buttons():
            self.unsetCursor()

        # --- اسمح بالانتشار إذا لم يتم التعامل مع الحدث ---
        if not (self.is_frameless and (self.resizing or self.drag_position is not None) and event.button() == Qt.MouseButton.LeftButton):
            super().mouseReleaseEvent(event)

    def sync_vk_lang_with_system(self, initial_setup=False):
        if not self.xkb_manager:
            if initial_setup: self.update_key_labels(); return
        current_sys_name = self.xkb_manager.query_current_layout_name(); new_vk_lang = self.current_language; manager_updated = False
        if current_sys_name:
            target_vk_lang = 'ar' if 'ar' in current_sys_name.lower() else 'en'; new_vk_lang = target_vk_lang
            available_layouts = self.xkb_manager.get_available_layouts()
            if current_sys_name in available_layouts:
                try:
                    sys_index = available_layouts.index(current_sys_name)
                    if self.xkb_manager.get_current_layout_index() != sys_index:
                        # print(f"Internal XKB update: {current_sys_name} ({sys_index})"); # Less verbose
                        self.xkb_manager.set_layout_by_index(sys_index, update_system=False); manager_updated = True
                except ValueError: pass
            else: print(f"WARN: System layout '{current_sys_name}' not cached.")
        if self.current_language != new_vk_lang or initial_setup:
            print(f"Update visual layout: {self.current_language} -> {new_vk_lang}"); self.current_language = new_vk_lang; self.update_key_labels()
        if manager_updated or initial_setup: self.update_tray_menu_check_state()

    def update_tray_menu_check_state(self):
        if not self.xkb_manager or not self.lang_action_group: return
        current_internal_name = self.xkb_manager.get_current_layout_name()
        if not current_internal_name: return
        action_to_check = self.language_actions.get(current_internal_name); checked_action = self.lang_action_group.checkedAction()
        if checked_action and checked_action != action_to_check:
            checked_action.blockSignals(True); checked_action.setChecked(False); checked_action.blockSignals(False)
        if action_to_check and not action_to_check.isChecked():
            action_to_check.blockSignals(True); action_to_check.setChecked(True); action_to_check.blockSignals(False)

    def check_system_layout(self):
        if not self.xkb_manager:
             if self.layout_check_timer.isActive(): self.layout_check_timer.stop(); return
        try:
            current_sys_name = self.xkb_manager.query_current_layout_name()
            internal_name = self.xkb_manager.get_current_layout_name()
            if current_sys_name and current_sys_name != internal_name:
                print(f"External layout change: {current_sys_name}. Syncing..."); self.sync_vk_lang_with_system()
        except Exception as e: pass

    def toggle_language(self):
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        if not self.xkb_manager:
             self.current_language = 'ar' if self.current_language == 'en' else 'en'; self.update_key_labels(); QMessageBox.information(self, "Layout Info", "XKB Manager unavailable."); return
        if len(self.xkb_manager.get_available_layouts()) <= 1:
             QMessageBox.information(self, "Layout Info", "Only one layout configured."); self.sync_vk_lang_with_system(); return
        print("Toggling language...");
        if not self.xkb_manager.cycle_next_layout(): QMessageBox.warning(self, "Layout Switch Failed", "setxkbmap command failed.")
        self.sync_vk_lang_with_system()

    def set_system_language_from_menu(self, lang_code):
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        if not self.xkb_manager: self.update_tray_menu_check_state(); return
        print(f"Tray: Setting layout to '{lang_code}'...");
        if not self.xkb_manager.set_layout_by_name(lang_code, update_system=True):
            QMessageBox.warning(self, "Layout Switch Failed", f"Could not switch to '{lang_code}'."); self.update_tray_menu_check_state()
        else: self.sync_vk_lang_with_system()
        # لا تظهر النافذة عند الاختيار من القائمة، اتركها مخفية إذا كانت مخفية
        # if self.isHidden(): self.show_normal_and_raise()

    def update_key_labels(self):
        symbol_map = { "Caps Lock": "⇪ Caps", "Tab": "⇥ Tab", "Enter": "↵ Enter", "Backspace": "⌫ Bksp", "Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "L Win": "◆", "R Win": "◆", "App": "☰", "Scroll Lock": "Scroll Lk", "Pause": "Pause", "PrtSc":"PrtSc", "Insert":"Ins", "Home":"Home", "Page Up":"PgUp", "Delete":"Del", "End":"End", "Page Down":"PgDn", "L Ctrl":"Ctrl", "R Ctrl":"Ctrl", "L Alt":"Alt", "R Alt":"AltGr", "Space":"Space", "Esc":"Esc", "About":"About", "Set":"Set", "LShift": "⇧ Shift", "RShift": "⇧ Shift", "Minimize":"_", "Close":"X", "Donate":"Donate"}
        for key_name, button in self.buttons.items():
            if not button: continue; new_label = key_name; toggled = False
            is_mod = key_name in ['LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock']
            if key_name == 'Lang': new_label = 'EN' if self.current_language == 'ar' else 'AR'
            elif key_name in ['LShift', 'RShift']: new_label="⇧ Shift"; toggled=self.shift_pressed
            elif key_name in ['L Ctrl', 'R Ctrl']: new_label="Ctrl"; toggled=self.ctrl_pressed
            elif key_name in ['L Alt', 'R Alt']: new_label="Alt" if key_name=='L Alt' else "AltGr"; toggled=self.alt_pressed
            elif key_name == 'Caps Lock': new_label=symbol_map.get(key_name, key_name); toggled=self.caps_lock_pressed
            elif key_name in KEY_CHAR_MAP: # Character keys
                char_map_for_key = KEY_CHAR_MAP[key_name]; char_tuple = char_map_for_key.get(self.current_language, char_map_for_key.get('en', (key_name,)*2))
                index_to_use = 0; is_letter = key_name.isalpha() and len(key_name)==1; effective_shift = (self.shift_pressed ^ self.caps_lock_pressed) if is_letter else self.shift_pressed
                if effective_shift and len(char_tuple) > 1: index_to_use = 1
                new_label = char_tuple[index_to_use] if index_to_use < len(char_tuple) else char_tuple[0]
            elif key_name in symbol_map: new_label = symbol_map[key_name] # Other symbol keys
            elif key_name.startswith("F") and key_name[1:].isdigit(): new_label = key_name
            if button.text() != new_label: button.setText(new_label)
            if is_mod:
                current_prop = button.property("modifier_on");
                if current_prop is None or current_prop != toggled: button.setProperty("modifier_on", toggled); button.style().unpolish(button); button.style().polish(button)

    def _simulate_single_key_press(self, key_name):
        if not key_name: return False
        is_letter = key_name.isalpha() and len(key_name)==1
        effective_shift = (self.shift_pressed ^ self.caps_lock_pressed) if is_letter else self.shift_pressed
        sim_ok = self._send_xtest_key(key_name, effective_shift)
        return sim_ok

    def _send_xtest_key(self, key_name, simulate_shift, is_caps_toggle=False):
        """ Sends the low-level XTEST key event sequence. Uses X_CONST alias now. """
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
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        sim_ok = self._send_xtest_key(key_name, False) # simulate_shift = False
        released_mods = False
        if sim_ok:
            # لا تقم بتحرير شيفت تلقائيًا عند الضغط على مفاتيح غير قابلة للتكرار
            # if self.shift_pressed: self.shift_pressed = False; released_mods = True
            if self.ctrl_pressed: self.ctrl_pressed = False; released_mods = True
            if self.alt_pressed: self.alt_pressed = False; released_mods = True
        if released_mods: self.update_key_labels()

    def _handle_key_pressed(self, key_name):
        if self.repeating_key_name and self.repeating_key_name != key_name:
            self._handle_key_released(self.repeating_key_name, force_stop=True)

        sim_ok = self._simulate_single_key_press(key_name)
        released_mods = False
        if sim_ok:
            # قم بتحرير المفاتيح المعدلة (عدا Caps Lock) بعد الضغط على مفتاح قابل للتكرار
            if self.shift_pressed: self.shift_pressed = False; released_mods = True
            if self.ctrl_pressed: self.ctrl_pressed = False; released_mods = True
            if self.alt_pressed: self.alt_pressed = False; released_mods = True
        if released_mods: self.update_key_labels()

        # بدء مؤقت التكرار فقط إذا نجحت المحاكاة وإذا تم تمكين التكرار
        if sim_ok and self.settings.get("auto_repeat_enabled", DEFAULT_SETTINGS.get("auto_repeat_enabled", True)):
            self.repeating_key_name = key_name
            self.initial_delay_timer.start()

    def _handle_key_released(self, key_name, force_stop=False):
        if force_stop or (self.repeating_key_name == key_name):
            if self.repeating_key_name: # Only act if a key was actually repeating
                self.initial_delay_timer.stop()
                self.auto_repeat_timer.stop()
                self.repeating_key_name = None

    def _trigger_initial_repeat(self):
        if self.repeating_key_name:
            self._simulate_single_key_press(self.repeating_key_name) # كرر الضغطة الأولى
            self.auto_repeat_timer.start() # ابدأ التكرار اللاحق
        else:
            # احتياطي: أوقف المؤقتات إذا كان المفتاح قد تم تحريره بالفعل
            self.initial_delay_timer.stop()
            self.auto_repeat_timer.stop()

    def _trigger_subsequent_repeat(self):
        if self.repeating_key_name:
            self._simulate_single_key_press(self.repeating_key_name) # كرر الضغطة
        else:
            # احتياطي: أوقف المؤقت إذا لم يعد هناك مفتاح للتكرار
            self.auto_repeat_timer.stop()

    def on_typable_key_right_press(self, key_name):
        print(f"Right-click detected on typable key: {key_name}")
        if self.repeating_key_name: self._handle_key_released(self.repeating_key_name, force_stop=True)
        # محاكاة الضغط مع شيفت
        sim_ok = self._send_xtest_key(key_name, True) # Simulate shift = True
        released_mods = False
        if sim_ok:
            # لا تقم بتحرير شيفت عند النقر بزر الماوس الأيمن
            # if self.shift_pressed: self.shift_pressed = False; released_mods = True
            if self.ctrl_pressed: self.ctrl_pressed = False; released_mods = True
            if self.alt_pressed: self.alt_pressed = False; released_mods = True
        if released_mods: self.update_key_labels()


# --- End of VirtualKeyboard Class ---
