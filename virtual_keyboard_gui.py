# -*- coding: utf-8 -*-
# file:virtual_keyboard_gui.py
# PyXKeyboard v1.0.7 - A simple, customizable on-screen virtual keyboard.
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.
# Main VirtualKeyboard class integrating UI, layout, simulation, dialogs, and tray.

import sys
import os
from typing import Optional, Tuple, Dict, List, Union
import copy

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QGridLayout, QMessageBox, QPushButton
    )
    from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSlot, QRect
    from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QScreen, QActionGroup 
    from PyQt6.QtWidgets import QSystemTrayIcon, QMenu 
except ImportError:
    print("ERROR: PyQt6 library is required for the main GUI.")
    raise

from .settings_manager import load_settings, save_settings, DEFAULT_SETTINGS
from . import xlib_integration as xlib_int
if not xlib_int.is_dummy():
    import Xlib 
    from Xlib import X as X_CONST_REAL 
else:
    Xlib = None
    X_CONST_REAL = xlib_int.X 

from .vk_ui import (
    init_ui_elements, apply_global_styles_and_font, load_initial_font_settings,
    apply_initial_geometry, center_window, load_app_icon,
    update_application_font, update_application_opacity, update_application_text_color,
    update_window_background_color, update_button_background_color, update_application_button_style,
    get_resize_edge, update_cursor_shape, EDGE_NONE, EDGE_TOP, EDGE_BOTTOM, EDGE_LEFT, EDGE_RIGHT, revert_button_flash
)
from .vk_layout_handling import (
    init_xkb_manager_and_layouts, update_key_labels_on_layout_change, update_single_key_label
)
from .vk_key_simulation import (
    on_modifier_key_press, on_non_repeatable_key_press,
    _send_xtest_key_event, _simulate_single_key_press_event,
    on_typable_key_right_press, _handle_key_pressed_simulation, _handle_key_released_simulation
)
from .vk_auto_repeat import (
    update_repeat_timers_from_settings,
    trigger_initial_repeat, trigger_subsequent_repeat
)
from .vk_dialogs import show_about_message, open_settings_dialog, open_donate_link
from .vk_tray_utils import (
    init_or_update_tray_icon, tray_icon_activated, 
    update_tray_menu_language_check_state, hide_to_tray,
    update_tray_status_display 
)


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


class VirtualKeyboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python XKeyboard")
        self.settings = load_settings()

        self.is_frameless = self.settings.get("frameless_window", DEFAULT_SETTINGS.get("frameless_window", False))
        self.always_on_top = self.settings.get("always_on_top", DEFAULT_SETTINGS.get("always_on_top", True))
        self.use_system_colors = self.settings.get("use_system_colors", DEFAULT_SETTINGS.get("use_system_colors", False))

        self.app_font = QFont()
        load_initial_font_settings(self) 

        xlib_int.initialize_xlib()
        self.xlib_ok = xlib_int.is_xtest_ok()
        self.is_xlib_dummy = xlib_int.is_dummy()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        base_flags = Qt.WindowType.Window | Qt.WindowType.WindowDoesNotAcceptFocus
        if self.always_on_top: base_flags |= Qt.WindowType.WindowStaysOnTopHint
        if self.is_frameless: base_flags |= Qt.WindowType.FramelessWindowHint
        else: base_flags |= (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)
        self.setWindowFlags(base_flags)

        self.resizing = False; self.resize_edge = EDGE_NONE; self.resize_start_pos = None; self.resize_start_geom = None
        self.resize_margin = 4 
        self.setMouseTracking(True) 

        self.buttons: Dict[str, QPushButton] = {}
        self.current_language = 'us' 
        self.shift_pressed = False; self.ctrl_pressed = False; self.alt_pressed = False; self.caps_lock_pressed = False
        self.drag_position: Optional[QPoint] = None
        
        self.xkb_manager = None 
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.icon: Optional[QIcon] = load_app_icon(self) 
        self.language_menu: Optional[QMenu] = None
        self.language_actions: Dict[str, QAction] = {}
        self.lang_action_group: Optional[QActionGroup] = None
        self.tray_menu: Optional[QMenu] = None

        self.focus_monitor: Optional[EditableFocusMonitor] = None
        self.focus_monitor_available = _focus_monitor_available
        self.monitor_was_running_for_context_menu = False 

        self.layout_check_timer: Optional[QTimer] = None 

        self.loaded_layouts: Dict[str, Dict[str, Union[list, tuple]]] = {} 
        self.layouts_dir = os.path.join(os.path.dirname(__file__), 'layouts')

        self.repeating_key_name: Optional[str] = None
        self.initial_delay_timer = QTimer(self); self.initial_delay_timer.setSingleShot(True)
        self.initial_delay_timer.timeout.connect(lambda: trigger_initial_repeat(self))
        self.auto_repeat_timer = QTimer(self)
        self.auto_repeat_timer.timeout.connect(lambda: trigger_subsequent_repeat(self))
        update_repeat_timers_from_settings(self) 

        init_xkb_manager_and_layouts(self) 

        self.central_widget = QWidget(); self.central_widget.setObjectName("centralWidget")
        self.central_widget.setMouseTracking(True); self.central_widget.setAutoFillBackground(True)
        self.setCentralWidget(self.central_widget)
        self.grid_layout = QGridLayout(self.central_widget)
        self.grid_layout.setSpacing(3); self.grid_layout.setContentsMargins(5, 5, 5, 5)

        self.init_focus_monitor() 
        apply_global_styles_and_font(self) 
        init_ui_elements(self) 

        if self.icon: self.setWindowIcon(self.icon)
        init_or_update_tray_icon(self) 
        apply_initial_geometry(self) 

        initial_lang_from_xkb = self.xkb_manager.get_current_layout_name() if self.xkb_manager else None
        final_initial_lang = 'us' 
        if initial_lang_from_xkb:
            if initial_lang_from_xkb in self.loaded_layouts:
                final_initial_lang = initial_lang_from_xkb
            elif 'us' in self.loaded_layouts: final_initial_lang = 'us'
            elif 'en' in self.loaded_layouts: final_initial_lang = 'en'
            elif self.loaded_layouts: final_initial_lang = next(iter(self.loaded_layouts))
        elif 'us' in self.loaded_layouts: final_initial_lang = 'us'
        elif 'en' in self.loaded_layouts: final_initial_lang = 'en'
        elif self.loaded_layouts: final_initial_lang = next(iter(self.loaded_layouts))

        self.sync_vk_lang_with_system_slot(final_initial_lang)
        self.update_key_labels() 

    # --- دالة جديدة لتنشيط النافذة ---
    def activate_and_show(self):
        """Brings the window to the front and ensures it's visible."""
        print("activate_and_show called on existing instance.")
        if self.isMinimized():
            self.showNormal() # استعادة من التصغير
        elif self.isHidden():
            self.show() # إظهار إذا كانت مخفية

        self.raise_() # رفع النافذة إلى المقدمة
        self.activateWindow() # محاولة تنشيط النافذة
        QApplication.setActiveWindow(self) # طريقة أخرى لمحاولة التنشيط
        print("Window should be activated and shown.")
    # --- نهاية الدالة الجديدة ---

    _apply_global_styles_and_font = apply_global_styles_and_font
    _load_initial_font_settings = load_initial_font_settings
    _apply_initial_geometry = apply_initial_geometry
    _center_window = center_window
    update_application_font = lambda self, font: update_application_font(self, font)
    update_application_opacity = lambda self, opacity: update_application_opacity(self, opacity)
    update_application_text_color = lambda self, color: update_application_text_color(self, color)
    update_window_background_color = lambda self, color: update_window_background_color(self, color)
    update_button_background_color = lambda self, color: update_button_background_color(self, color)
    update_application_button_style = lambda self, style: update_application_button_style(self, style)
    _get_resize_edge = lambda self, pos: get_resize_edge(self, pos)
    _update_cursor_shape = lambda self, edge: update_cursor_shape(self, edge)
    _revert_button_flash = lambda self, btn, style: revert_button_flash(self, btn, style)

    _init_xkb_manager = lambda self: init_xkb_manager_and_layouts(self) 
    update_key_labels = lambda self: update_key_labels_on_layout_change(self)
    update_single_key_label = lambda self, key_name: update_single_key_label(self, key_name)

    on_modifier_key_press = lambda self, key_name: on_modifier_key_press(self, key_name)
    on_non_repeatable_key_press = lambda self, key_name: on_non_repeatable_key_press(self, key_name)
    _send_xtest_key = lambda self, key_name, shift, is_caps=False: _send_xtest_key_event(self, key_name, shift, is_caps)
    _simulate_single_key_press_event = lambda self, key_name: _simulate_single_key_press_event(self, key_name)
    on_typable_key_right_press = lambda self, key_name: on_typable_key_right_press(self, key_name)
    _handle_key_pressed = lambda self, key_name: _handle_key_pressed_simulation(self, key_name)
    _handle_key_released = lambda self, key_name, force_stop=False: _handle_key_released_simulation(self, key_name, force_stop)

    _update_repeat_timers_from_settings = lambda self: update_repeat_timers_from_settings(self)
    
    show_about_message = lambda self: show_about_message(self)
    open_settings_dialog = lambda self: open_settings_dialog(self)
    _open_donate_link = lambda self: open_donate_link(self)

    init_tray_icon = lambda self: init_or_update_tray_icon(self) 
    tray_icon_activated = lambda self, reason: tray_icon_activated(self, reason)
    _update_tray_menu_language_check_state = lambda self: update_tray_menu_language_check_state(self) 
    hide_to_tray = lambda self: hide_to_tray(self)
    _update_tray_status_display = lambda self: update_tray_status_display(self)


    def _pause_focus_monitor_if_running(self) -> bool:
        if self.focus_monitor and self.focus_monitor.is_running():
            print("Pausing AT-SPI focus monitor for dialog/menu...")
            try:
                self.focus_monitor.stop()
                return True
            except Exception as e:
                print(f"ERROR stopping focus monitor: {e}")
        return False

    def _resume_focus_monitor_if_needed(self, was_running_before: bool):
        setting_is_enabled = self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
        if was_running_before and setting_is_enabled:
            print("Resuming AT-SPI focus monitor...")
            if self.focus_monitor:
                try:
                    if not self.focus_monitor.is_running():
                        self.focus_monitor.start()
                    if not self.focus_monitor.is_running(): 
                        print("WARNING: Could not resume AT-SPI focus monitor.")
                except Exception as e:
                    print(f"ERROR resuming focus monitor: {e}")
            else: 
                print("Cannot resume focus monitor, instance is missing.")
        elif was_running_before and not setting_is_enabled:
            print("Focus monitor was running but is now disabled by settings. Ensuring it's stopped.")
            if self.focus_monitor and self.focus_monitor.is_running():
                try: self.focus_monitor.stop()
                except Exception as e: print(f"ERROR ensuring disabled focus monitor is stopped: {e}")


    def init_focus_monitor(self):
        if not _focus_monitor_available or EditableFocusMonitor is None:
            print("Focus monitor skipped (module or dependencies unavailable).")
            self.focus_monitor = None
            self.focus_monitor_available = False 
            return

        try:
            self.focus_monitor = EditableFocusMonitor(self._handle_editable_focus_event)
            print("EditableFocusMonitor instance created.")
            self.focus_monitor_available = True 

            if self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False)):
                print("Auto-show on edit is enabled, attempting to start AT-SPI monitor...")
                self.focus_monitor.start()
                if not self.focus_monitor.is_running():
                    print("WARNING: Could not start AT-SPI focus monitor after initialization attempt.")
            else:
                print("Auto-show on edit is disabled in settings.")
        except ImportError as e: 
            print(f"Focus monitor disabled due to import error: {e}", file=sys.stderr)
            self.focus_monitor = None
            self.focus_monitor_available = False
        except Exception as e: 
            print(f"ERROR initializing or starting AT-SPI focus monitor: {e}", file=sys.stderr)
            self.focus_monitor = None
            self.focus_monitor_available = False


    def _handle_editable_focus_event(self, accessible_object): 
        if self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False)):
            if self.isHidden() or self.isMinimized():
                print("Editable field focused (AT-SPI), showing keyboard...")
                QTimer.singleShot(50, self.show_normal_and_raise)

    def show_normal_and_raise(self):
        if self.isHidden() or self.isMinimized():
            self.showNormal()
        self.activateWindow() 
        self.raise_()         


    def _apply_settings_from_dialog(self, applied_settings: dict):
        print("Applying settings from dialog...")
        previous_frameless = self.is_frameless
        previous_on_top = self.always_on_top
        previous_auto_show = self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))

        self.settings = copy.deepcopy(applied_settings) 

        self.is_frameless = self.settings.get("frameless_window", DEFAULT_SETTINGS.get("frameless_window", False))
        self.always_on_top = self.settings.get("always_on_top", DEFAULT_SETTINGS.get("always_on_top", True))
        
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
            print("Window flags (frameless/always_on_top) changed, re-applying...")
            base_flags = Qt.WindowType.Window | Qt.WindowType.WindowDoesNotAcceptFocus
            if self.always_on_top: base_flags |= Qt.WindowType.WindowStaysOnTopHint
            if self.is_frameless: base_flags |= Qt.WindowType.FramelessWindowHint
            else: base_flags |= (Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)
            
            current_visibility = self.isVisible()
            self.hide() 
            self.setWindowFlags(base_flags)
            self._apply_global_styles_and_font() 

            for key_name_btn in ['Minimize', 'Close']:
                if key_name_btn in self.buttons:
                    self.buttons[key_name_btn].setVisible(self.is_frameless)
            print("Custom Minimize/Close button visibility updated based on frameless state.")
            
            if current_visibility: 
                QTimer.singleShot(50, self.show) 
            else:
                print("Window was hidden, keeping it hidden after flag change.")
        else: 
            self._apply_global_styles_and_font()
            self.update_key_labels() 
            print("Styles and labels updated (no window flag change).")
        
        current_auto_show = self.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
        if current_auto_show != previous_auto_show:
            if current_auto_show:
                if self.focus_monitor and not self.focus_monitor.is_running():
                    print("Auto-show enabled in settings, starting AT-SPI monitor...")
                    self.focus_monitor.start()
                    if not self.focus_monitor.is_running():
                        print("WARNING: Failed to start AT-SPI monitor after enabling in settings.")
            else:
                if self.focus_monitor and self.focus_monitor.is_running():
                    print("Auto-show disabled in settings, stopping AT-SPI monitor...")
                    self.focus_monitor.stop()
        
        self.init_tray_icon() 

    @pyqtSlot(str)
    def sync_vk_lang_with_system_slot(self, new_layout_name: Optional[str] = None):
        if not self.xkb_manager: return

        current_sys_name = new_layout_name if new_layout_name is not None else self.xkb_manager.query_current_layout_name()

        if current_sys_name:
            target_vk_lang = current_sys_name
            layout_exists = target_vk_lang in self.loaded_layouts
            
            if not layout_exists: 
                if target_vk_lang.startswith('en') and 'us' in self.loaded_layouts: target_vk_lang = 'us'; layout_exists = True
                elif 'us' in self.loaded_layouts: target_vk_lang = 'us'; layout_exists = True
                elif 'en' in self.loaded_layouts: target_vk_lang = 'en'; layout_exists = True
                elif self.loaded_layouts: 
                    target_vk_lang = next(iter(self.loaded_layouts)); layout_exists = True
            
            if not layout_exists: 
                print(f"Error: No suitable visual layout found for system layout '{current_sys_name}' and no fallbacks loaded. Cannot update display.", file=sys.stderr)
                target_vk_lang = 'us' 

            if self.current_language != target_vk_lang:
                print(f"Visual layout changing: {self.current_language} -> {target_vk_lang} (due to system: {current_sys_name})")
                self.current_language = target_vk_lang
                self.update_key_labels() 

            if new_layout_name is None and self.xkb_manager.get_current_layout_name() != current_sys_name:
                if current_sys_name in self.xkb_manager.get_available_layouts():
                    try:
                        sys_index = self.xkb_manager.get_available_layouts().index(current_sys_name)
                        self.xkb_manager._set_internal_index(sys_index, emit_signal=False)
                    except ValueError: 
                        pass
                else: 
                    print(f"Sync Warning: Queried system layout '{current_sys_name}' not in XKBManager's known list. Attempting refresh.", file=sys.stderr)
                    self.xkb_manager.refresh() 
        else:
            print("WARNING: Could not query current system layout during sync.")

        self._update_tray_status_display() 

    @pyqtSlot()
    def check_system_layout_timer_slot(self):
        if not self.xkb_manager or self.xkb_manager.can_monitor(): 
            if self.layout_check_timer and self.layout_check_timer.isActive():
                self.layout_check_timer.stop()
            return

        current_sys_name = self.xkb_manager.query_current_layout_name()
        internal_xkb_name = self.xkb_manager.get_current_layout_name()

        if current_sys_name and current_sys_name != internal_xkb_name:
            print(f"Polling Timer: Detected system layout change ({internal_xkb_name} -> {current_sys_name}). Syncing VK...")
            self.sync_vk_lang_with_system_slot() 

    def toggle_language(self):
        if self.repeating_key_name: 
            self._handle_key_released(self.repeating_key_name, force_stop=True)

        if not self.xkb_manager: 
            codes = list(self.loaded_layouts.keys())
            if not codes: codes = ['us'] 
            try:
                idx = codes.index(self.current_language)
            except ValueError:
                idx = -1 
            next_idx = (idx + 1) % len(codes)
            self.current_language = codes[next_idx]
            self.update_key_labels()
            QMessageBox.information(self, "Layout Info", "XKB Layout Manager unavailable. Cycled internal display only.")
            return

        if len(self.xkb_manager.get_available_layouts()) <= 1:
            QMessageBox.information(self, "Layout Info", "Only one system layout is configured.")
            self.sync_vk_lang_with_system_slot() 
            return
        
        print("Toggling system language...")
        if not self.xkb_manager.cycle_next_layout(): 
            QMessageBox.warning(self, "Layout Switch Failed",
                                f"'{self.xkb_manager.get_current_method()}' command to switch layout failed.")
        
        if not self.xkb_manager.can_monitor():
            QTimer.singleShot(100, self.sync_vk_lang_with_system_slot) 

    def set_system_language_from_menu(self, lang_code: str):
        if self.repeating_key_name:
            self._handle_key_released(self.repeating_key_name, force_stop=True)
        
        if not self.xkb_manager:
            self._update_tray_status_display() 
            return

        print(f"Tray Menu: Attempting to set system layout to '{lang_code}'...")
        if not self.xkb_manager.set_layout_by_name(lang_code, update_system=True):
            QMessageBox.warning(self, "Layout Switch Failed",
                                f"Could not switch to '{lang_code}' using '{self.xkb_manager.get_current_method()}'.")
        
        if not self.xkb_manager.can_monitor():
            QTimer.singleShot(100, self.sync_vk_lang_with_system_slot)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            if self.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True)):
                self.hide_to_tray()
                event.accept()
                return
        elif event.button() == Qt.MouseButton.RightButton:
            target_widget = self.childAt(event.position().toPoint())
            is_background_click = (target_widget is self or target_widget is self.central_widget or target_widget is None)
            
            if self.tray_menu and is_background_click:
                self.monitor_was_running_for_context_menu = self._pause_focus_monitor_if_running()
                
                try: self.tray_menu.aboutToHide.disconnect(self._resume_monitor_after_context_menu)
                except (TypeError, RuntimeError): pass 
                self.tray_menu.aboutToHide.connect(self._resume_monitor_after_context_menu)

                self.tray_menu.popup(event.globalPosition().toPoint())
                event.accept()
                return
        elif event.button() == Qt.MouseButton.LeftButton:
            local_pos = event.position().toPoint()
            if self.is_frameless: 
                self.resize_edge = self._get_resize_edge(local_pos)
                if self.resize_edge != EDGE_NONE:
                    self.resizing = True
                    self.resize_start_pos = event.globalPosition().toPoint()
                    self.resize_start_geom = self.geometry()
                    self._update_cursor_shape(self.resize_edge)
                    print(f"Starting frameless resize from edge: {self.resize_edge}")
                    event.accept()
                    return
            
            target_widget = self.childAt(local_pos)
            is_button_click = isinstance(target_widget, QPushButton) if target_widget else False
            is_background_click = (target_widget is self.central_widget or target_widget is self or target_widget is None) and not is_button_click

            if is_background_click:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                print("Starting window drag (Left Button on background)")
                event.accept()
                return
        
        super().mousePressEvent(event) 

    def _resume_monitor_after_context_menu(self):
        print("Context menu closed.")
        try:
            if self.tray_menu: self.tray_menu.aboutToHide.disconnect(self._resume_monitor_after_context_menu)
        except (TypeError, RuntimeError): pass
        
        self._resume_focus_monitor_if_needed(self.monitor_was_running_for_context_menu)
        self.monitor_was_running_for_context_menu = False 


    def mouseMoveEvent(self, event):
        if self.repeating_key_name and self.buttons.get(self.repeating_key_name):
            button_being_repeated = self.buttons[self.repeating_key_name]
            if not button_being_repeated.rect().contains(button_being_repeated.mapFromGlobal(event.globalPosition().toPoint())):
                self._handle_key_released(self.repeating_key_name, force_stop=True) 

        if self.is_frameless and self.resizing and event.buttons() == Qt.MouseButton.LeftButton:
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self.resize_start_pos
            new_geom = QRect(self.resize_start_geom) 

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
            
            self.setGeometry(new_geom)
            event.accept()
            return
        elif self.drag_position is not None and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            event.accept()
            return
        elif self.is_frameless and not self.resizing and self.drag_position is None: 
            current_edge = self._get_resize_edge(event.position().toPoint())
            self._update_cursor_shape(current_edge)
        
        if not (self.is_frameless and (self.resizing or self.drag_position is not None)):
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event):
        if self.repeating_key_name: 
            self._handle_key_released(self.repeating_key_name, force_stop=True)

        if self.is_frameless and self.resizing and event.button() == Qt.MouseButton.LeftButton:
            self.resizing = False
            self.resize_edge = EDGE_NONE 
            self.resize_start_pos = None
            self.resize_start_geom = None
            self.unsetCursor() 
            print("Frameless resize finished.")
            event.accept()
            return
        elif self.drag_position is not None and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = None
            print("Window drag finished.")
            event.accept()
            return
        elif self.is_frameless and not self.resizing and not event.buttons(): 
            self.unsetCursor() 

        if not (self.is_frameless and (self.resizing or self.drag_position is not None) and event.button() == Qt.MouseButton.LeftButton):
            super().mouseReleaseEvent(event)


    def closeEvent(self, event):
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore() 
            self.hide_to_tray()
        else: 
            event.accept()
            self.quit_application() 

    def quit_application(self):
        print("Quit application requested...")

        if self.xkb_manager and self.xkb_manager.can_monitor():
            self.xkb_manager.stop_change_monitor()
        elif self.layout_check_timer and self.layout_check_timer.isActive():
            self.layout_check_timer.stop()
        
        if hasattr(self, 'initial_delay_timer'): self.initial_delay_timer.stop()
        if hasattr(self, 'auto_repeat_timer'): self.auto_repeat_timer.stop()

        if self.focus_monitor and self.focus_monitor.is_running():
            try:
                self.focus_monitor.stop()
            except Exception as e:
                print(f"Error stopping AT-SPI focus monitor during quit: {e}")

        if self.settings.get("remember_geometry", DEFAULT_SETTINGS.get("remember_geometry", True)):
            try:
                if not self.isMinimized(): 
                    self.settings["window_geometry"] = {
                        "x": self.geometry().x(), "y": self.geometry().y(),
                        "width": self.geometry().width(), "height": self.geometry().height()
                    }
            except Exception as e:
                self.settings["window_geometry"] = None 
                print(f"ERROR getting window geometry on quit: {e}")
        else:
            self.settings["window_geometry"] = None 

        save_settings(self.settings) 
        
        if self.tray_icon:
            self.tray_icon.hide() 
            self.tray_icon.deleteLater() 

        xlib_int.close_xlib() 
        print("PyXKeyboard application quitting.")
        
        instance = QApplication.instance()
        if instance:
            instance.quit() 