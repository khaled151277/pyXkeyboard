# -*- coding: utf-8 -*-
# Contains the main VirtualKeyboard class, UI, event handling, and integration logic.

import sys
import os
from typing import Optional # Make sure Optional is imported
import re
import copy

try:
    # Import necessary PyQt6 modules
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QPushButton, QGridLayout, QSizePolicy,
        QSystemTrayIcon, QMenu, QMessageBox
    )
    from PyQt6.QtCore import Qt, QSize, QEvent, QPoint, QTimer, pyqtSignal
    from PyQt6.QtGui import (
        QFont, QPalette, QColor, QIcon, QAction,
        QPixmap, QPainter, QFontMetrics, QScreen,
        QActionGroup, QPen, QBrush # Added QPen, QBrush for icon drawing
    )
    from PyQt6.QtWidgets import QStyle # For style polishing
except ImportError:
    print("ERROR: PyQt6 library is required for the main GUI.")
    print("Please install it: pip install PyQt6")
    raise

# --- Local Project Imports ---
from settings_manager import load_settings, save_settings, DEFAULT_SETTINGS
from settings_dialog import SettingsDialog
from key_definitions import KEYBOARD_LAYOUT, KEY_CHAR_MAP, X11_KEYSYM_MAP
# --- Import X along with the module alias ---
import xlib_integration as xlib_int
from xlib_integration import X # Import X specifically
# --- END MODIFICATION ---
from XKB_Switcher import XKBManager, XKBManagerError # System layout switching

# --- Optional Focus Monitor Import ---
_focus_monitor_available = False # Default to False
try:
    from focus_monitor import EditableFocusMonitor # For auto-show feature
    _focus_monitor_available = True
    print("Focus monitor module loaded successfully.")
except ImportError as e:
    print(f"WARNING: Could not import EditableFocusMonitor: {e}")
    print("Auto-show keyboard feature will be disabled.")
    EditableFocusMonitor = None
except Exception as e:
    print(f"WARNING: Unexpected error importing EditableFocusMonitor: {e}")
    EditableFocusMonitor = None
# --- End Import ---


# --- Custom QPushButton subclass for right-click detection ---
class RightClickButton(QPushButton):
    """ A QPushButton that emits a 'rightClicked' signal on right mouse press. """
    rightClicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, event):
        """ Override mouse press event to detect right clicks. """
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

# --- Main Application Window ---
class VirtualKeyboard(QMainWindow):
    """ Main application window class for the virtual keyboard. """
    def __init__(self):
        """ Initialize the main window, load settings, set up components. """
        super().__init__()
        self.setWindowTitle("Python XKeyboard")

        self.settings = load_settings()
        self.app_font = QFont()

        xlib_int.initialize_xlib()
        self.xlib_ok = xlib_int.is_xtest_ok()
        self.is_xlib_dummy = xlib_int.is_dummy()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
             Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint |
             Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint |
             Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        # Initialize state variables
        self.buttons = {}
        self.current_language = 'en'
        self.shift_pressed = False
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.caps_lock_pressed = False
        self.drag_position = None
        self.xkb_manager = None
        self.tray_icon = None
        self.icon = None # Initialize icon attribute
        self.language_menu = None
        self.language_actions = {}
        self.lang_action_group = None
        self.focus_monitor = None
        self.focus_monitor_available = _focus_monitor_available

        self.load_initial_font_settings()
        self.init_xkb_manager()

        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)
        self.grid_layout = QGridLayout(self.central_widget)
        self.grid_layout.setSpacing(3)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)

        self.init_focus_monitor()

        self._apply_global_styles_and_font()

        self.init_ui()
        # Generate icon before initializing tray
        self.icon = self.generate_keyboard_icon() # Generate new icon
        self.init_tray_icon() # Initialize tray uses self.icon

        self.apply_initial_geometry()

        self.layout_check_timer = QTimer(self)
        self.layout_check_timer.timeout.connect(self.check_system_layout)
        if self.xkb_manager:
             self.layout_check_timer.start(1000)

    def load_initial_font_settings(self):
        """ Loads font family and size from settings into self.app_font. """
        font_family = self.settings.get("font_family", DEFAULT_SETTINGS["font_family"])
        font_size = self.settings.get("font_size", DEFAULT_SETTINGS["font_size"])
        try:
            self.app_font = QFont(font_family, font_size)
            print(f"Loaded font settings: Family='{self.app_font.family()}', Size={self.app_font.pointSize()}pt")
            self.settings["font_family"] = self.app_font.family()
            self.settings["font_size"] = self.app_font.pointSize()
        except Exception as e:
            print(f"ERROR creating font '{font_family}' {font_size}pt: {e}. Using default.")
            self.app_font = QFont(DEFAULT_SETTINGS["font_family"], DEFAULT_SETTINGS["font_size"])
            self.settings["font_family"] = self.app_font.family()
            self.settings["font_size"] = self.app_font.pointSize()

    def apply_initial_geometry(self):
        """ Applies saved window geometry or defaults. """
        initial_geom_applied = False
        if self.settings.get("remember_geometry"):
            geom = self.settings.get("window_geometry")
            if geom and isinstance(geom, dict) and all(k in geom for k in ["x", "y", "width", "height"]):
                try:
                    print(f"Applying saved geometry: {geom}")
                    self.setGeometry(geom["x"], geom["y"], geom["width"], geom["height"])
                    self.setMinimumSize(400, 130)
                    initial_geom_applied = True
                except Exception as e:
                    print(f"ERROR applying saved geometry: {e}. Using defaults.")
                    self.settings["window_geometry"] = None

        if not initial_geom_applied:
            print("Applying default geometry.")
            self.resize(900, 140)
            self.setMinimumSize(400, 130)
            self.center_window()

    def init_xkb_manager(self):
        """ Initializes the XKBManager if available. """
        if XKBManager:
            try:
                self.xkb_manager = XKBManager(auto_refresh=False)
                if self.xkb_manager.refresh():
                     initial_layout = self.xkb_manager.query_current_layout_name()
                     if initial_layout:
                         self.xkb_manager.set_layout_by_name(initial_layout, update_system=False)
                     print(f"XKBManager Initialized: SUCCESS (Layouts: {self.xkb_manager.get_available_layouts()})")
                else:
                     print("XKBManager Initialized: ERROR - Initial refresh failed.")
                     self.xkb_manager = None
            except (XKBManagerError, Exception) as e:
                print(f"XKBManager Initialized: ERROR - {e}")
                self.xkb_manager = None
        else:
            print("XKBManager Initialized: Module not found (Layout switching disabled).")
            self.current_language = 'en'

    def init_focus_monitor(self):
        """ Initializes the EditableFocusMonitor if available and enabled. """
        if not self.focus_monitor_available or not EditableFocusMonitor:
            print("Focus monitor initialization skipped (module not available).")
            return

        try:
            self.focus_monitor = EditableFocusMonitor(self._handle_editable_focus)
            print("EditableFocusMonitor instance created.")

            if self.settings.get("auto_show_on_edit", False):
                print("Auto-show enabled in settings, attempting to start monitor...")
                self.focus_monitor.start()
                if not self.focus_monitor.is_running():
                    QMessageBox.warning(self, "Focus Monitor Failed",
                                        "Could not start the focus monitor.\n"
                                        "Auto-show feature might not work.\n"
                                        "Check if AT-SPI services are running.")
            else:
                print("Auto-show disabled in settings, monitor not started initially.")

        except Exception as e:
            print(f"ERROR initializing or starting EditableFocusMonitor: {e}")
            QMessageBox.critical(self, "Focus Monitor Error",
                                 f"Failed to initialize the focus monitor:\n{e}\n"
                                 "The auto-show feature will be disabled.")
            self.focus_monitor = None
            self.focus_monitor_available = False

    def _handle_editable_focus(self, accessible):
        """ Callback executed by EditableFocusMonitor. """
        if self.settings.get("auto_show_on_edit", False):
            if self.isHidden() or not self.isActiveWindow():
                QTimer.singleShot(0, self.show_normal_and_activate)

    def _apply_global_styles_and_font(self):
        """ Applies base font and stylesheet to the central widget. """
        # print("Applying global styles and font...") # Reduce noise
        if not self.central_widget: return

        text_color = self.settings.get("text_color", DEFAULT_SETTINGS["text_color"])
        button_style_name = self.settings.get("button_style", DEFAULT_SETTINGS["button_style"])
        opacity_level = self.settings.get("window_opacity", DEFAULT_SETTINGS["window_opacity"])
        font_family = self.app_font.family()
        font_size = self.app_font.pointSize()

        base_button_style_parts = [
            f"color: {text_color};",
            f"font-family: '{font_family}';",
            f"font-size: {font_size}pt;",
        ]
        if button_style_name == "flat":
            base_button_style_parts.extend([
                "border: 1px solid #888888;", "background-color: #e0e0e0;", "border-radius: 3px;"
            ])
        elif button_style_name == "gradient":
            base_button_style_parts.extend([
                "border: 1px solid #aaaaaa;",
                """background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f8f8f8, stop: 1 #dddddd);""",
                "border-radius: 4px;"
            ])
        base_button_style = " ".join(base_button_style_parts)
        toggled_modifier_style = "background-color: #add8e6; border: 1px solid #00008b;"

        alpha_value = int(max(0.0, min(1.0, opacity_level)) * 255)
        palette = self.palette()
        base_color = palette.color(QPalette.ColorRole.Window)
        background_rgba = f"rgba({base_color.red()}, {base_color.green()}, {base_color.blue()}, {alpha_value})"
        central_widget_bg_style = f"background-color: {background_rgba}; border-radius: 5px;"

        full_stylesheet = f"""
            QWidget#centralWidget {{ {central_widget_bg_style} }}
            QPushButton {{ {base_button_style} padding: 2px; }}
            QPushButton[modifier_on="true"] {{ {toggled_modifier_style} }}
        """
        self.central_widget.setStyleSheet(full_stylesheet)

    def update_application_font(self, new_font):
        """ Internal update for font object. """
        self.app_font = QFont(new_font)

    def update_application_opacity(self, opacity_level):
        """ Internal update for opacity setting. """
        self.settings["window_opacity"] = max(0.0, min(1.0, opacity_level))

    def update_application_text_color(self, color_str):
        """ Internal update for text color setting. """
        if not (isinstance(color_str, str) and color_str.startswith('#') and (len(color_str) == 7 or len(color_str) == 9)):
             color_str = DEFAULT_SETTINGS["text_color"]
        self.settings["text_color"] = color_str

    def update_application_button_style(self, style_name):
        """ Internal update for button style setting. """
        valid_styles = ["default", "flat", "gradient"]
        if style_name not in valid_styles: style_name = "default"
        self.settings["button_style"] = style_name

    def center_window(self):
        """ Centers the window on the primary screen. """
        try:
            screen = QApplication.primaryScreen()
            if screen:
                center_point = screen.availableGeometry().center()
                frame_geo = self.frameGeometry()
                top_left = center_point - frame_geo.center() + frame_geo.topLeft()
                self.move(top_left)
            else: print("WARNING: Could not get primary screen info to center window.")
        except Exception as e: print(f"WARNING: Error centering window: {e}")

    def generate_keyboard_icon(self, size=32):
        """ Generates a simple light blue keyboard icon. """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        body_color = QColor("#ADD8E6") # LightBlue
        border_color = QColor("#607B8B") # SlateGray4
        key_color = QColor("#404040") # Dark gray

        body_rect_margin_float = size * 0.1
        body_rect_margin = int(body_rect_margin_float) # Cast to int
        body_rect = pixmap.rect().adjusted(body_rect_margin, body_rect_margin, -body_rect_margin, -body_rect_margin)

        key_width_f = body_rect.width() * 0.18
        key_height_f = body_rect.height() * 0.18
        key_h_spacing_f = body_rect.width() * 0.07
        key_v_spacing_f = body_rect.height() * 0.09
        base_x_f = body_rect.left() + key_h_spacing_f * 1.5
        base_y_f = body_rect.top() + key_v_spacing_f * 1.5

        painter.setBrush(QBrush(body_color))
        painter.setPen(QPen(border_color, max(1, int(size * 0.05)))) # Cast pen width
        painter.drawRoundedRect(body_rect, size * 0.1, size * 0.1)

        painter.setBrush(QBrush(key_color))
        painter.setPen(Qt.PenStyle.NoPen)
        for r in range(2):
            for c in range(3):
                key_x = base_x_f + c * (key_width_f + key_h_spacing_f)
                key_y = base_y_f + r * (key_height_f + key_v_spacing_f)
                painter.drawRect(int(key_x), int(key_y), int(key_width_f), int(key_height_f)) # Cast all to int
        space_y = base_y_f + 2 * (key_height_f + key_v_spacing_f)
        space_width = key_width_f * 2 + key_h_spacing_f
        painter.drawRect(int(base_x_f), int(space_y), int(space_width), int(key_height_f)) # Cast all to int

        painter.end()
        return QIcon(pixmap)

    # --- MODIFIED: init_ui to fix F-key labels ---
    def init_ui(self):
        """ Creates and lays out the keyboard buttons. """
        symbol_map = {
            "Caps Lock": "⇪ Caps", "Tab": "⇥ Tab", "Enter": "↵ Enter",
            "Backspace": "⌫ Bksp","Up": "↑", "Down": "↓", "Left": "←", "Right": "→",
            "L Win": "◆", "R Win": "◆","App": "☰", "Scroll Lock": "Scroll Lk",
            "Pause": "Pause", "PrtSc":"PrtSc","Insert":"Ins", "Home":"Home",
            "Page Up":"PgUp", "Delete":"Del", "End":"End","Page Down":"PgDn",
            "L Ctrl":"Ctrl", "R Ctrl":"Ctrl", "L Alt":"Alt", "R Alt":"AltGr",
            "Space":"Space", "Esc":"Esc", "About":"About", "Set":"Set",
            "LShift": "⇧ Shift", "RShift": "⇧ Shift"
        }

        self.buttons = {}
        while self.grid_layout.count():
             item = self.grid_layout.takeAt(0); widget = item.widget()
             if widget: widget.deleteLater()

        for r, row_keys in enumerate(KEYBOARD_LAYOUT):
            col = 0
            for key_data in row_keys:
                if key_data:
                    key_name, row_span, col_span = key_data

                    # --- Determine initial label CORRECTLY ---
                    if key_name in symbol_map:
                        initial_label = symbol_map[key_name]
                    # Explicitly check for F-keys before defaulting
                    elif key_name.startswith("F") and key_name[1:].isdigit():
                         initial_label = key_name # Use "F1", "F2" etc. as label
                    elif key_name == "Lang":
                        initial_label = "Lang" # Placeholder, updated later
                    else:
                        # Default to the key_name itself if not in map and not F-key
                        initial_label = key_name
                    # --- End Label Determination ---

                    is_typable_key = key_name in KEY_CHAR_MAP
                    button = RightClickButton(initial_label) if is_typable_key else QPushButton(initial_label)

                    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    button.setFocusPolicy(Qt.FocusPolicy.NoFocus); button.setAutoRepeat(False)

                    is_modifier_key = key_name in ['LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock']
                    if is_modifier_key: button.setProperty("modifier_on", False)

                    if key_name == 'Lang': button.clicked.connect(self.toggle_language)
                    elif key_name == 'About': button.clicked.connect(self.show_about_message)
                    elif key_name == 'Set': button.clicked.connect(self.open_settings_dialog)
                    else:
                        button.clicked.connect(lambda chk=False, k=key_name: self.on_key_press(k))
                        if isinstance(button, RightClickButton): button.rightClicked.connect(lambda k=key_name: self.on_key_right_press(k))

                    self.grid_layout.addWidget(button, r, col, row_span, col_span)
                    self.buttons[key_name] = button; col += col_span
                else: col += 1

        if self.xkb_manager: self.sync_vk_lang_with_system(initial_setup=True)
        else: self.update_key_labels()


    def init_tray_icon(self):
        """ Initializes or updates the system tray icon and menu. """
        if not QSystemTrayIcon.isSystemTrayAvailable():
            if self.tray_icon is None: print("System Tray: Not available on this system.")
            self.tray_icon = None; return

        if not self.tray_icon:
             self.tray_icon = QSystemTrayIcon(self)
             try:
                 if not self.icon: self.icon = self.generate_keyboard_icon() # Use new icon
                 self.tray_icon.setIcon(self.icon); self.setWindowIcon(self.icon)
             except Exception as e: print(f"System Tray: ERROR setting icon: {e}")

             self.tray_menu = QMenu(self); self.language_menu = None
             self.language_actions = {}; self.lang_action_group = None
             if self.xkb_manager:
                 layouts = self.xkb_manager.get_available_layouts()
                 if layouts:
                     self.language_menu = QMenu("Select Layout", self)
                     self.lang_action_group = QActionGroup(self); self.lang_action_group.setExclusive(True)
                     for lc in layouts:
                         a = QAction(lc, self, checkable=True)
                         a.triggered.connect(lambda checked=False, l=lc: self.set_system_language_from_menu(l))
                         self.language_menu.addAction(a); self.language_actions[lc] = a; self.lang_action_group.addAction(a)
                     self.tray_menu.addMenu(self.language_menu); self.tray_menu.addSeparator()

             about_action = QAction("About...", self) # Add About action
             about_action.triggered.connect(self.show_about_message)
             self.tray_menu.addAction(about_action) # Add it to menu

             show_act = QAction("Show Keyboard", self); show_act.triggered.connect(self.show_normal_and_activate)
             quit_act = QAction("Quit", self); quit_act.triggered.connect(self.quit_application)
             self.tray_menu.addSeparator() # Separator
             self.tray_menu.addActions([show_act, quit_act]) # Add Show and Quit

             self.tray_icon.setContextMenu(self.tray_menu)
             self.tray_icon.activated.connect(self.tray_icon_activated)
             try: self.tray_icon.show()
             except Exception as e: print(f"System Tray: ERROR showing icon: {e}")

        tooltip_parts = [self.windowTitle()]
        if self.xkb_manager: tooltip_parts.append("Layout Sync")
        if self.xlib_ok: tooltip_parts.append("XInput")
        elif not self.is_xlib_dummy: tooltip_parts.append("XInput ERR")
        if self.focus_monitor_available:
             setting_enabled = self.settings.get("auto_show_on_edit", False)
             monitor_active = self.focus_monitor and self.focus_monitor.is_running()
             if setting_enabled and monitor_active: status = "Active"
             elif setting_enabled and not monitor_active: status = "Enabled (Inactive)"
             else: status = "Disabled"
             tooltip_parts.append(f"AT-SPI {status}")
        else: tooltip_parts.append("AT-SPI N/A")
        try: self.tray_icon.setToolTip(" | ".join(tooltip_parts))
        except Exception as e: print(f"System Tray: ERROR setting tooltip: {e}")

        self.update_tray_menu_check_state()

    def tray_icon_activated(self, reason):
        """ Handles clicks on the system tray icon. """
        if reason == QSystemTrayIcon.ActivationReason.Trigger: self.show_normal_and_activate()

    def show_normal_and_activate(self):
        """ Shows the window normally and brings it to the front. """
        if self.isHidden(): self.showNormal()
        self.activateWindow(); self.raise_()

    def closeEvent(self, event):
        """ Overrides the window close event to hide to tray. """
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore(); self.hide()
            try: self.tray_icon.showMessage(self.windowTitle(),"Minimized to system tray.", self.icon if self.icon else QIcon(), 2000)
            except Exception as e: print(f"Tray message display failed: {e}")
        else: self.quit_application()

    def quit_application(self):
        """ Cleans up resources and exits the application properly. """
        print("Quit requested. Cleaning up...")
        if hasattr(self, 'layout_check_timer'): self.layout_check_timer.stop()
        if self.focus_monitor and self.focus_monitor.is_running(): self.focus_monitor.stop()
        if self.settings.get("remember_geometry"):
            try: self.settings["window_geometry"] = {"x": self.geometry().x(), "y": self.geometry().y(), "width": self.geometry().width(), "height": self.geometry().height()}
            except Exception as e: self.settings["window_geometry"] = None; print(f"ERROR getting geometry on exit: {e}")
        else: self.settings["window_geometry"] = None
        save_settings(self.settings)
        if self.tray_icon: self.tray_icon.hide()
        xlib_int.close_xlib()
        print("Quitting application...")
        QApplication.instance().quit()

    def show_about_message(self):
        """ Shows the 'About' dialog, pausing the focus monitor temporarily. """
        program_name = self.windowTitle()

        monitor_was_running = False
        if self.focus_monitor and self.focus_monitor.is_running():
            print("Pausing focus monitor for About dialog...")
            try: self.focus_monitor.stop(); monitor_was_running = True
            except Exception as e: print(f"ERROR stopping focus monitor: {e}")

        try:
            status_xkb="N/A"; status_xtest="N/A"; status_auto_show="N/A"
            if XKBManager is None: status_xkb = "Disabled (Module XKB_Switcher not found)"
            elif self.xkb_manager: status_xkb = f"Enabled (Layouts: {', '.join(self.xkb_manager.get_available_layouts() or ['None found'])})"
            else: status_xkb = "Disabled (Initialization error)"

            if self.is_xlib_dummy: status_xtest = "Disabled (python-xlib not found)"
            elif self.xlib_ok: status_xtest = "Enabled"
            else: status_xtest = "Disabled (Initialization error or missing keycodes)"

            if not self.focus_monitor_available: status_auto_show = "Disabled (AT-SPI monitor unavailable/failed)"
            elif self.focus_monitor or monitor_was_running:
                 setting_enabled = self.settings.get("auto_show_on_edit", False)
                 if setting_enabled and monitor_was_running: status_auto_show = "Enabled (Active - Paused for Dialog)"
                 elif setting_enabled and not monitor_was_running: status_auto_show = "Enabled (Inactive - Monitor Error?)"
                 else: status_auto_show = "Disabled (in Settings)"
            else: status_auto_show = "Disabled (Monitor init failed)"

            main_info = f"""<p><b>{program_name} v1.01</b><br>A simple on-screen virtual keyboard.</p><p>Developed by: Khaled Abdelhamid<br>Contact: <a href="mailto:khaled1512@gmail.com">khaled1512@gmail.com</a></p><p><b>License:</b><br>GNU General Public License v3 (GPLv3)</p><p><b>Disclaimer:</b><br>Provided 'as is' without warranty. Use at your own risk.</p><p>Support development via PayPal:<br><a href="https://paypal.me/kh1512">https://paypal.me/kh1512</a><br>(Copy: <code>paypal.me/kh1512</code>)</p><p>Thank you!</p>"""
            full_message = main_info + "<hr>" + f"""<p><b>Status:</b><br>Layout Control (XKB): {status_xkb}<br>Input Simulation (XTEST): {status_xtest}<br>Auto-Show (AT-SPI): {status_auto_show}</p>"""
            QMessageBox.information(self, f"About {program_name}", full_message)

        finally:
            setting_is_enabled = self.settings.get("auto_show_on_edit", False)
            if monitor_was_running and setting_is_enabled:
                print("Resuming focus monitor after About dialog...")
                if self.focus_monitor:
                    try:
                        self.focus_monitor.start()
                        if not self.focus_monitor.is_running(): QMessageBox.warning(self, "Focus Monitor Failed","Could not resume monitor.")
                    except Exception as e: print(f"ERROR resuming focus monitor: {e}")
                else: print("Cannot resume focus monitor, instance is missing.")
            self.init_tray_icon() # Update tooltip

    def open_settings_dialog(self):
        """ Opens the settings dialog, pausing the focus monitor temporarily. """
        dialog = SettingsDialog(self.settings, self.app_font, self.focus_monitor_available, self)
        dialog.settingsApplied.connect(self._apply_settings_from_dialog)

        monitor_was_running = False
        if self.focus_monitor and self.focus_monitor.is_running():
            print("Pausing focus monitor for settings dialog...")
            try: self.focus_monitor.stop(); monitor_was_running = True
            except Exception as e: print(f"ERROR stopping focus monitor: {e}")

        try:
            dialog.exec()
        finally:
            setting_is_enabled_after_dialog = self.settings.get("auto_show_on_edit", False)
            if monitor_was_running and setting_is_enabled_after_dialog:
                print("Resuming focus monitor after settings dialog...")
                if self.focus_monitor:
                    try:
                        self.focus_monitor.start()
                        if not self.focus_monitor.is_running(): QMessageBox.warning(self, "Focus Monitor Failed", "Could not resume monitor.")
                    except Exception as e: print(f"ERROR resuming focus monitor: {e}")
                else: print("Cannot resume focus monitor, instance is missing.")
            elif monitor_was_running and not setting_is_enabled_after_dialog:
                 print("Focus monitor was running but setting is now disabled. Not resuming.")

            self.init_tray_icon() # Update tooltip
            try: dialog.settingsApplied.disconnect(self._apply_settings_from_dialog)
            except TypeError: pass


    def _apply_settings_from_dialog(self, applied_settings):
        """ Applies settings received after SettingsDialog is accepted. """
        print("Applying settings received from dialog...")

        new_font = QFont(
            self.settings.get("font_family", DEFAULT_SETTINGS["font_family"]),
            self.settings.get("font_size", DEFAULT_SETTINGS["font_size"])
        )
        if new_font != self.app_font: self.update_application_font(new_font)
        self.update_application_opacity(self.settings.get("window_opacity", DEFAULT_SETTINGS["window_opacity"]))
        self.update_application_text_color(self.settings.get("text_color", DEFAULT_SETTINGS["text_color"]))
        self.update_application_button_style(self.settings.get("button_style", DEFAULT_SETTINGS["button_style"]))

        self._apply_global_styles_and_font()
        self.update_key_labels()


    # --- Mouse Handling ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            if self.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS["auto_hide_on_middle_click"]):
                self.hide(); event.accept(); return
        elif event.button() == Qt.MouseButton.LeftButton:
            target = self.childAt(event.position().toPoint())
            if target is self.central_widget or target is None:
                 self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                 event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.drag_position = None; event.accept()
        else: super().mouseReleaseEvent(event)

    # --- Keyboard Functionality ---
    def sync_vk_lang_with_system(self, initial_setup=False):
        """ Matches VK display to system layout. """
        if not self.xkb_manager:
            if initial_setup: self.update_key_labels(); return

        current_sys = self.xkb_manager.query_current_layout_name()
        new_vk_lang = self.current_language; manager_updated = False
        if current_sys:
            new_vk_lang = 'ar' if 'ar' in current_sys.lower() else 'en'
            available = self.xkb_manager.get_available_layouts()
            if current_sys in available:
                 try:
                      idx = available.index(current_sys)
                      if self.xkb_manager.get_current_layout_index() != idx:
                          self.xkb_manager.set_layout_by_index(idx, update_system=False); manager_updated = True
                 except ValueError:
                     if self.xkb_manager.refresh():
                        try:
                           idx = self.xkb_manager.get_available_layouts().index(current_sys)
                           self.xkb_manager.set_layout_by_index(idx, update_system=False); manager_updated = True
                        except ValueError: pass

        if self.current_language != new_vk_lang or initial_setup:
            self.current_language = new_vk_lang; self.update_key_labels()
        if manager_updated or initial_setup: self.update_tray_menu_check_state()

    def update_tray_menu_check_state(self):
        """ Updates the tray menu language checkmark. """
        if not self.xkb_manager or not self.lang_action_group: return
        current_name = self.xkb_manager.get_current_layout_name()
        action_to_check = self.language_actions.get(current_name)
        checked_action = self.lang_action_group.checkedAction()
        if checked_action and checked_action != action_to_check:
             checked_action.blockSignals(True); checked_action.setChecked(False); checked_action.blockSignals(False)
        if action_to_check and not action_to_check.isChecked():
            action_to_check.blockSignals(True); action_to_check.setChecked(True); action_to_check.blockSignals(False)

    def check_system_layout(self):
        """ Timer callback to detect external layout changes. """
        if not self.xkb_manager:
             if self.layout_check_timer.isActive(): self.layout_check_timer.stop(); return
        try:
            current_sys = self.xkb_manager.query_current_layout_name()
            if current_sys and current_sys != self.xkb_manager.get_current_layout_name(): self.sync_vk_lang_with_system()
        except Exception: pass

    def toggle_language(self):
        """ Handles 'Lang' button click. """
        if not self.xkb_manager:
            self.current_language = 'ar' if self.current_language == 'en' else 'en'; self.update_key_labels()
            QMessageBox.information(self, "Layout Info", "System layout switching is disabled."); return
        if len(self.xkb_manager.get_available_layouts()) <= 1:
             QMessageBox.information(self, "Layout Info", "Only one system layout configured."); self.sync_vk_lang_with_system(); return
        if not self.xkb_manager.cycle_next_layout(): QMessageBox.warning(self, "Layout Switch Failed", "Could not change system layout.")
        self.sync_vk_lang_with_system()

    def set_system_language_from_menu(self, lang_code):
        """ Handles tray menu language selection. """
        if not self.xkb_manager: self.update_tray_menu_check_state(); return
        print(f"Tray Menu: Setting system layout to '{lang_code}'...")
        if not self.xkb_manager.set_layout_by_name(lang_code, update_system=True):
             QMessageBox.warning(self, "Layout Switch Failed", f"Could not switch system layout to '{lang_code}'.")
        elif self.isHidden(): self.show_normal_and_activate()
        self.sync_vk_lang_with_system()

    def update_key_labels(self):
        """ Updates button text and dynamic properties only. """
        symbol_map = { "Caps Lock": "⇪ Caps", "Tab": "⇥ Tab", "Enter": "↵ Enter", "Backspace": "⌫ Bksp", "Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "L Win": "◆", "R Win": "◆", "App": "☰", "Scroll Lock": "Scroll Lk", "Pause": "Pause", "PrtSc":"PrtSc", "Insert":"Ins", "Home":"Home", "Page Up":"PgUp", "Delete":"Del", "End":"End", "Page Down":"PgDn", "L Ctrl":"Ctrl", "R Ctrl":"Ctrl", "L Alt":"Alt", "R Alt":"AltGr", "Space":"Space", "Esc":"Esc", "About":"About", "Set":"Set", }
        for key_name, button in self.buttons.items():
            if not button: continue; new_label = key_name; toggled = False
            is_mod = key_name in ['LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock']
            if key_name == 'Lang': new_label = 'EN' if self.current_language == 'ar' else 'AR'
            elif key_name in ['LShift', 'RShift']: new_label="⇧ Shift"; toggled=self.shift_pressed
            elif key_name in ['L Ctrl', 'R Ctrl']: new_label="Ctrl"; toggled=self.ctrl_pressed
            elif key_name in ['L Alt', 'R Alt']: new_label="Alt" if key_name=='L Alt' else "AltGr"; toggled=self.alt_pressed
            elif key_name == 'Caps Lock': new_label=symbol_map[key_name]; toggled=self.caps_lock_pressed
            elif key_name in KEY_CHAR_MAP:
                cmap=KEY_CHAR_MAP[key_name]; ctuple=cmap.get(self.current_language, cmap.get('en', (key_name,)*2))
                idx=0; is_ltr=key_name.isalpha() and len(key_name)==1
                use_shift = (self.shift_pressed ^ self.caps_lock_pressed) if is_ltr else self.shift_pressed
                if use_shift and len(ctuple)>1: idx=1
                new_label = ctuple[idx] if idx < len(ctuple) else ctuple[0]
            elif key_name in symbol_map: new_label = symbol_map[key_name]
            # --- Fix: Check if F-key before defaulting label ---
            elif key_name.startswith("F") and key_name[1:].isdigit():
                 new_label = key_name # Ensure F-keys keep their names
            # --- End Fix ---

            if button.text() != new_label: button.setText(new_label)
            if is_mod:
                prop=button.property("modifier_on")
                if prop != toggled: button.setProperty("modifier_on", toggled); button.style().unpolish(button); button.style().polish(button)

    def _send_xtest_key(self, key_name, simulate_shift, is_caps_toggle=False):
        """ Simulates a key press/release via XTEST. """
        caps_kc, shift_kc, ctrl_kc, alt_kc = (xlib_int.get_caps_lock_keycode(), xlib_int.get_shift_keycode(), xlib_int.get_ctrl_keycode(), xlib_int.get_alt_keycode())
        if is_caps_toggle:
             if not self.xlib_ok or not caps_kc: return False
             ok = xlib_int.send_xtest_event(X.KeyPress, caps_kc) and xlib_int.send_xtest_event(X.KeyRelease, caps_kc)
             if not ok: self._handle_xtest_error(); return False
             return True
        if not self.xlib_ok: return False
        keysym = X11_KEYSYM_MAP.get(key_name)
        if keysym is None or keysym == 0: return False
        kc = xlib_int.keysym_to_keycode(keysym)
        if not kc: print(f"WARNING: No KeyCode for {hex(keysym)} ('{key_name}')."); return False
        needs_shift = simulate_shift; ok = True
        try:
            if self.ctrl_pressed and ctrl_kc: ok &= xlib_int.send_xtest_event(X.KeyPress, ctrl_kc)
            if self.alt_pressed and alt_kc: ok &= xlib_int.send_xtest_event(X.KeyPress, alt_kc)
            if needs_shift and shift_kc: ok &= xlib_int.send_xtest_event(X.KeyPress, shift_kc)
            if not ok: raise Exception("Modifiers Press")
            ok &= xlib_int.send_xtest_event(X.KeyPress, kc) and xlib_int.send_xtest_event(X.KeyRelease, kc)
            if not ok: raise Exception("Target Key Press/Release")
            if needs_shift and shift_kc: ok &= xlib_int.send_xtest_event(X.KeyRelease, shift_kc)
            if self.alt_pressed and alt_kc: ok &= xlib_int.send_xtest_event(X.KeyRelease, alt_kc)
            if self.ctrl_pressed and ctrl_kc: ok &= xlib_int.send_xtest_event(X.KeyRelease, ctrl_kc)
            if not ok: raise Exception("Modifiers Release")
            return True
        except Exception as e:
            print(f"ERROR during XTEST sequence for '{key_name}': {e}"); self._handle_xtest_error()
            try: # Cleanup attempt
                if needs_shift and shift_kc: xlib_int.send_xtest_event(X.KeyRelease, shift_kc)
                if self.alt_pressed and alt_kc: xlib_int.send_xtest_event(X.KeyRelease, alt_kc)
                if self.ctrl_pressed and ctrl_kc: xlib_int.send_xtest_event(X.KeyRelease, ctrl_kc)
            except Exception: pass
            return False

    def _handle_xtest_error(self, critical=False):
        """ Disables XTEST on error. """
        if self.xlib_ok:
            self.xlib_ok = False; print("XTEST disabled due to error."); xlib_int.flush_display()
            msg = "Connection to X server lost." if critical else "Error during key simulation."
            QMessageBox.warning(self, "XTEST Error", f"{msg}\nXTEST is now disabled."); self.init_tray_icon()

    def on_key_press(self, key_name):
        """ Handles left-clicks. """
        mod_changed = False
        if key_name in ['LShift', 'RShift']: self.shift_pressed = not self.shift_pressed; mod_changed=True
        elif key_name in ['L Ctrl', 'R Ctrl']: self.ctrl_pressed = not self.ctrl_pressed; mod_changed=True
        elif key_name in ['L Alt', 'R Alt']: self.alt_pressed = not self.alt_pressed; mod_changed=True
        elif key_name == 'Caps Lock':
            self.caps_lock_pressed = not self.caps_lock_pressed
            if not self._send_xtest_key(key_name, False, True): self.caps_lock_pressed = not self.caps_lock_pressed # Revert
            mod_changed=True
        if mod_changed: self.update_key_labels(); return
        eff_shift = self.shift_pressed ^ self.caps_lock_pressed if (key_name.isalpha() and len(key_name)==1) else self.shift_pressed
        sim_ok = self._send_xtest_key(key_name, eff_shift)
        released = False
        if sim_ok:
            if self.shift_pressed: self.shift_pressed = False; released = True
            if self.ctrl_pressed: self.ctrl_pressed = False; released = True
            if self.alt_pressed: self.alt_pressed = False; released = True
        if released: self.update_key_labels()

    def on_key_right_press(self, key_name):
        """ Handles right-clicks (Shift + Key). """
        sim_ok = self._send_xtest_key(key_name, True) # Force shift
        released = False
        if sim_ok:
            if self.ctrl_pressed: self.ctrl_pressed = False; released = True
            if self.alt_pressed: self.alt_pressed = False; released = True
        if released: self.update_key_labels()
