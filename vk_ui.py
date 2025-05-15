# -*- coding: utf-8 -*-
# file: vk_ui.py
# PyXKeyboard v1.0.7 - UI Setup and Styling for VirtualKeyboard
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

import os
from pathlib import Path
try:
    from PyQt6.QtWidgets import (
        QPushButton, QSizePolicy, QMessageBox, QWidget, QGridLayout
    )
    from PyQt6.QtCore import Qt, QSize, QTimer
    from PyQt6.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QPainter, QBrush, QPen, QCursor # Added QBrush, QPen
except ImportError:
    print("ERROR: PyQt6 library is required for vk_ui.")
    raise

from .key_definitions import KEYBOARD_LAYOUT, FALLBACK_CHAR_MAP
from .settings_manager import DEFAULT_SETTINGS

EDGE_NONE = 0; EDGE_TOP = 1; EDGE_BOTTOM = 2; EDGE_LEFT = 4; EDGE_RIGHT = 8
EDGE_TOP_LEFT = EDGE_TOP | EDGE_LEFT; EDGE_TOP_RIGHT = EDGE_TOP | EDGE_RIGHT
EDGE_BOTTOM_LEFT = EDGE_BOTTOM | EDGE_LEFT; EDGE_BOTTOM_RIGHT = EDGE_BOTTOM | EDGE_RIGHT

# --- UI Initialization and Styling ---

def _normalize_hex_color(color_str: str, default_color: str) -> str:
    """Validates a hex color string and returns it, or a default if invalid."""
    if isinstance(color_str, str) and \
       color_str.startswith('#') and \
       (len(color_str) == 7 or len(color_str) == 9): # #RRGGBB or #AARRGGBB
        try:
            QColor(color_str) # Attempt to create QColor to validate fully
            return color_str
        except Exception:
            # Will fall through to return default_color
            pass 
    print(f"Warning: Invalid hex color string '{color_str}'. Using default '{default_color}'.")
    return default_color


def init_ui_elements(vk_instance):
    """Initializes the UI elements (buttons) for the virtual keyboard."""
    symbol_map = {
        "Caps Lock": "⇪ Caps", "Tab": "⇥ Tab", "Enter": "↵ Enter", "Backspace": "⌫ Bksp",
        "Up": "↑", "Down": "↓", "Left": "←", "Right": "→",
        "L Win": "◆", "R Win": "◆", "App": "☰", "Scroll Lock": "Scroll Lk",
        "Pause": "Pause", "PrtSc":"PrtSc", "Insert":"Ins", "Home":"Home",
        "Page Up":"PgUp", "Delete":"Del", "End":"End", "Page Down":"PgDn",
        "L Ctrl":"Ctrl", "R Ctrl":"Ctrl", "L Alt":"Alt", "R Alt":"AltGr",
        "Space":"Space", "Esc":"Esc", "About":"About", "Set":"Set",
        "LShift": "⇧ Shift", "RShift": "⇧ Shift",
        "Minimize":"_", "Close":"X", "Donate":"Donate"
    }
    vk_instance.buttons = {} 

    while vk_instance.grid_layout.count():
        item = vk_instance.grid_layout.takeAt(0)
        if item is not None:
            widget = item.widget()
            if widget:
                widget.deleteLater()

    repeatable_keys = set(FALLBACK_CHAR_MAP.keys()) | {'Space', 'Backspace', 'Delete', 'Tab', 'Enter', 'Up', 'Down', 'Left', 'Right'}
    non_repeatable_functional_keys = {
        'Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
        'PrtSc', 'Scroll Lock', 'Pause', 'Insert', 'Home', 'Page Up', 'End', 'Page Down',
        'L Win', 'R Win', 'App'
    }
    modifier_keys = {'LShift', 'RShift', 'L Ctrl', 'R Ctrl', 'L Alt', 'R Alt', 'Caps Lock'}
    special_action_keys = {'About', 'Set', 'Minimize', 'Close', 'Donate'}
    lang_keys = {'Lang1', 'Lang2', 'Lang3'}

    for r, row_keys in enumerate(KEYBOARD_LAYOUT):
        col = 0
        for key_data in row_keys:
            if key_data:
                key_name, row_span, col_span = key_data
                initial_label = symbol_map.get(key_name, key_name)
                if key_name.startswith("F") and key_name[1:].isdigit():
                    initial_label = key_name
                elif key_name.startswith("Lang"):
                    initial_label = "Lang" 

                button = QPushButton(initial_label)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                button.setAutoRepeat(False) 

                if key_name in special_action_keys:
                    if key_name == 'About': button.clicked.connect(vk_instance.show_about_message)
                    elif key_name == 'Set': button.clicked.connect(vk_instance.open_settings_dialog)
                    elif key_name == 'Minimize': button.clicked.connect(vk_instance.hide_to_tray); button.setObjectName("MinimizeButton")
                    elif key_name == 'Close': button.clicked.connect(vk_instance.quit_application); button.setObjectName("CloseButton")
                    elif key_name == 'Donate': button.clicked.connect(vk_instance._open_donate_link); button.setObjectName("DonateButton")
                elif key_name in lang_keys:
                    button.clicked.connect(vk_instance.toggle_language)
                elif key_name in modifier_keys:
                    button.setProperty("modifier_on", False) 
                    button.clicked.connect(lambda chk=False, k=key_name: vk_instance.on_modifier_key_press(k))
                elif key_name in repeatable_keys: 
                    button.pressed.connect(lambda k=key_name: vk_instance._handle_key_pressed(k))
                    button.released.connect(lambda k=key_name: vk_instance._handle_key_released(k))
                    if key_name in FALLBACK_CHAR_MAP: 
                        button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                        button.customContextMenuRequested.connect(
                            lambda pos, k=key_name: vk_instance.on_typable_key_right_press(k)
                        )
                elif key_name in non_repeatable_functional_keys:
                    button.clicked.connect(lambda chk=False, k=key_name: vk_instance.on_non_repeatable_key_press(k))
                else:
                    print(f"Warning: Key '{key_name}' has no defined action.")


                vk_instance.grid_layout.addWidget(button, r, col, row_span, col_span)
                vk_instance.buttons[key_name] = button

                if key_name in ['Minimize', 'Close']:
                    button.setVisible(vk_instance.is_frameless) 

                col += col_span
            else: 
                col += 1
    apply_global_styles_and_font(vk_instance) 

def apply_global_styles_and_font(vk_instance):
    if not vk_instance.central_widget:
        return

    use_system_colors = vk_instance.settings.get("use_system_colors", DEFAULT_SETTINGS.get("use_system_colors", False))
    
    default_text_color = DEFAULT_SETTINGS.get("text_color", "#000000")
    custom_text_color_setting = vk_instance.settings.get("text_color", default_text_color)
    final_text_color_str = _normalize_hex_color(custom_text_color_setting, default_text_color)

    button_style_name = vk_instance.settings.get("button_style", DEFAULT_SETTINGS.get("button_style", "default"))
    opacity_level = vk_instance.settings.get("window_opacity", DEFAULT_SETTINGS.get("window_opacity", 1.0))

    font_family = vk_instance.app_font.family()
    font_size = vk_instance.app_font.pointSize()

    default_win_bg = DEFAULT_SETTINGS.get("window_background_color", "#F0F0F0")
    window_bg_color_setting = vk_instance.settings.get("window_background_color", default_win_bg)
    
    default_btn_bg = DEFAULT_SETTINGS.get("button_background_color", "#E1E1E1")
    button_bg_color_setting = vk_instance.settings.get("button_background_color", default_btn_bg)


    common_button_style_parts = [
        f"color: {final_text_color_str};",
        f"font-family: '{font_family}';",
        f"font-size: {font_size}pt;",
        "padding: 2px;"
    ]
    button_specific_style_parts = []
    base_button_style = ""

    if not use_system_colors:
        normalized_button_bg = _normalize_hex_color(button_bg_color_setting, default_btn_bg)
        if button_style_name == "flat":
            button_specific_style_parts.extend([
                f"background-color: {normalized_button_bg};",
                "border: 1px solid #aaaaaa;", "border-radius: 3px;"
            ])
        elif button_style_name == "gradient":
            button_specific_style_parts.extend([
                "border: 1px solid #bbbbbb;",
                "background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #fefefe, stop: 1 #e0e0e0);", # Gradient uses its own bg
                "border-radius: 4px;"
            ])
        else: 
            button_specific_style_parts.append(f"background-color: {normalized_button_bg};")
            button_specific_style_parts.append("border: 1px solid #C0C0C0;")
        base_button_style = " ".join(common_button_style_parts + button_specific_style_parts)
    else:
        base_button_style = " ".join(common_button_style_parts)

    toggled_modifier_style = "background-color: #a0cfeC !important; border: 1px solid #0000A0 !important; font-weight: bold;"
    custom_control_style = f"font-weight: bold; font-size: 10pt; color: {final_text_color_str};" 
    donate_style = "font-size: 10pt; font-weight: bold; background-color: yellow; color: black !important; border: 1px solid #A0A000;"

    alpha_value = int(max(0.0, min(1.0, opacity_level)) * 255)
    final_window_bg_rgba = "rgba(0,0,0,0)" 

    if not use_system_colors:
        normalized_window_bg = _normalize_hex_color(window_bg_color_setting, default_win_bg)
        try:
            base_window_color = QColor(normalized_window_bg)
            final_window_bg_rgba = f"rgba({base_window_color.red()}, {base_window_color.green()}, {base_window_color.blue()}, {alpha_value})"
        except Exception as e:
            print(f"Error applying custom window background color '{normalized_window_bg}': {e}")
    else:
        palette = vk_instance.palette()
        base_color = palette.color(QPalette.ColorRole.Window)
        final_window_bg_rgba = f"rgba({base_color.red()}, {base_color.green()}, {base_color.blue()}, {alpha_value})"

    bg_style = f"background-color: {final_window_bg_rgba} !important;"
    vk_instance.central_widget.setStyleSheet(f"QWidget#centralWidget {{ {bg_style} }}")
    vk_instance.central_widget.setAutoFillBackground(True) 

    full_stylesheet = f"""
        QPushButton {{ {base_button_style} }}
        QPushButton {{ color: {final_text_color_str}; }} 
        QPushButton:pressed {{ background-color: #cceeff !important; border: 1px solid #88aabb !important; }}
        QPushButton[modifier_on="true"] {{ {toggled_modifier_style} }}
        QPushButton#MinimizeButton, QPushButton#CloseButton {{ {custom_control_style} }}
        QPushButton#DonateButton {{ {donate_style} }}
    """
    vk_instance.setStyleSheet(full_stylesheet)


def load_initial_font_settings(vk_instance):
    font_family = vk_instance.settings.get("font_family", DEFAULT_SETTINGS.get("font_family", "Sans Serif"))
    font_size = vk_instance.settings.get("font_size", DEFAULT_SETTINGS.get("font_size", 9))
    try:
        vk_instance.app_font.setFamily(font_family)
        vk_instance.app_font.setPointSize(font_size)
        print(f"Loaded font: {vk_instance.app_font.family()} {vk_instance.app_font.pointSize()}pt")
    except Exception as e:
        print(f"ERROR creating font: {e}. Using default.")
        vk_instance.app_font.setFamily(DEFAULT_SETTINGS.get("font_family", "Sans Serif"))
        vk_instance.app_font.setPointSize(DEFAULT_SETTINGS.get("font_size", 9))

def apply_initial_geometry(vk_instance):
    initial_geom_applied = False
    min_width, min_height = 400, 130 

    if vk_instance.settings.get("remember_geometry", DEFAULT_SETTINGS.get("remember_geometry", True)):
        geom = vk_instance.settings.get("window_geometry")
        if geom and isinstance(geom, dict) and all(k in geom for k in ["x", "y", "width", "height"]):
            try:
                width = max(min_width, geom["width"])
                height = max(min_height, geom["height"])
                print(f"Applying saved geometry: x={geom['x']}, y={geom['y']}, w={width}, h={height}")
                vk_instance.setGeometry(geom["x"], geom["y"], width, height)
                initial_geom_applied = True
            except Exception as e:
                print(f"ERROR applying saved geometry: {e}.")
                vk_instance.settings["window_geometry"] = None 
        else: 
             print("Ignoring invalid saved geometry.")
             vk_instance.settings["window_geometry"] = None

    if not initial_geom_applied:
        print("Applying default geometry.")
        vk_instance.resize(900, 180) 
        center_window(vk_instance)

    vk_instance.setMinimumSize(min_width, min_height)

def center_window(vk_instance):
    try:
        screen = vk_instance.screen() 
        if not screen:
            from PyQt6.QtWidgets import QApplication 
            screen = QApplication.primaryScreen()

        if screen:
            available_geom = screen.availableGeometry()
            center_point = available_geom.center()
            frame_geo = vk_instance.frameGeometry()
            top_left = center_point - frame_geo.center() + frame_geo.topLeft()
            top_left.setX(max(available_geom.left(), min(top_left.x(), available_geom.right() - frame_geo.width())))
            top_left.setY(max(available_geom.top(), min(top_left.y(), available_geom.bottom() - frame_geo.height())))
            vk_instance.move(top_left)
        else:
            print("WARNING: Could not get primary screen info to center window.")
    except Exception as e:
        print(f"WARNING: Error centering window: {e}")


def load_app_icon(vk_instance):
    icon = QIcon()
    script_dir = os.path.dirname(os.path.abspath(__file__)) 
    icon_dir = os.path.join(script_dir, 'icons')
    icon_files = [
        os.path.join(icon_dir, "icon_32.png"), os.path.join(icon_dir, "icon_64.png"),
        os.path.join(icon_dir, "icon_128.png"), os.path.join(icon_dir, "icon_256.png"),
    ]
    found_any = False
    for file_path in icon_files:
        if os.path.exists(file_path):
            icon.addFile(file_path)
            found_any = True

    if found_any:
        print("Icon loaded successfully.")
        return icon
    else:
        print("No icon files found. Generating default.")
        return generate_keyboard_icon()

def generate_keyboard_icon(size=32):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent) 
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    body_color = QColor("#ADD8E6") 
    border_color = QColor("#607B8B") 
    key_color = QColor("#404040")    

    body_rect_margin = int(size * 0.1)
    body_rect = pixmap.rect().adjusted(body_rect_margin, body_rect_margin, -body_rect_margin, -body_rect_margin)
    painter.setBrush(QBrush(body_color))
    painter.setPen(QPen(border_color, max(1, int(size * 0.05)))) 
    painter.drawRoundedRect(body_rect, size * 0.1, size * 0.1) 

    key_width_f = body_rect.width() * 0.18
    key_height_f = body_rect.height() * 0.18
    key_h_spacing_f = body_rect.width() * 0.07
    key_v_spacing_f = body_rect.height() * 0.09

    base_x_f = body_rect.left() + key_h_spacing_f * 1.5
    base_y_f = body_rect.top() + key_v_spacing_f * 1.5

    painter.setBrush(QBrush(key_color))
    painter.setPen(Qt.PenStyle.NoPen) 

    for r_idx in range(2): 
        for c_idx in range(3): 
            key_x = base_x_f + c_idx * (key_width_f + key_h_spacing_f)
            key_y = base_y_f + r_idx * (key_height_f + key_v_spacing_f)
            painter.drawRect(int(key_x), int(key_y), int(key_width_f), int(key_height_f))

    space_y = base_y_f + 2 * (key_height_f + key_v_spacing_f)
    space_width = key_width_f * 2 + key_h_spacing_f 
    painter.drawRect(int(base_x_f), int(space_y), int(space_width), int(key_height_f))

    painter.end()
    return QIcon(pixmap)


def update_application_font(vk_instance, new_font):
    vk_instance.app_font = QFont(new_font)

def update_application_opacity(vk_instance, opacity_level):
    vk_instance.settings["window_opacity"] = max(0.0, min(1.0, opacity_level))

def update_application_text_color(vk_instance, color_str):
    default_text_color = DEFAULT_SETTINGS.get("text_color", "#000000")
    vk_instance.settings["text_color"] = _normalize_hex_color(color_str, default_text_color)

def update_window_background_color(vk_instance, color_str):
    default_win_bg = DEFAULT_SETTINGS.get("window_background_color", "#F0F0F0")
    vk_instance.settings["window_background_color"] = _normalize_hex_color(color_str, default_win_bg)

def update_button_background_color(vk_instance, color_str):
    default_btn_bg = DEFAULT_SETTINGS.get("button_background_color", "#E1E1E1")
    vk_instance.settings["button_background_color"] = _normalize_hex_color(color_str, default_btn_bg)

def update_application_button_style(vk_instance, style_name):
    valid_styles = ["default", "flat", "gradient"]
    if style_name not in valid_styles:
        style_name = DEFAULT_SETTINGS.get("button_style", "default")
    vk_instance.settings["button_style"] = style_name


def get_resize_edge(vk_instance, pos):
    if not vk_instance.is_frameless:
        return EDGE_NONE
    rect = vk_instance.rect()
    margin = vk_instance.resize_margin

    on_top = pos.y() < margin
    on_bottom = pos.y() > rect.bottom() - margin
    on_left = pos.x() < margin
    on_right = pos.x() > rect.right() - margin

    edge = EDGE_NONE
    if on_top: edge |= EDGE_TOP
    if on_bottom: edge |= EDGE_BOTTOM
    if on_left: edge |= EDGE_LEFT
    if on_right: edge |= EDGE_RIGHT
    return edge

def update_cursor_shape(vk_instance, edge):
    cursor_shape = Qt.CursorShape.ArrowCursor
    if vk_instance.is_frameless:
        if edge == EDGE_TOP or edge == EDGE_BOTTOM:
            cursor_shape = Qt.CursorShape.SizeVerCursor
        elif edge == EDGE_LEFT or edge == EDGE_RIGHT:
            cursor_shape = Qt.CursorShape.SizeHorCursor
        elif edge == EDGE_TOP_LEFT or edge == EDGE_BOTTOM_RIGHT:
            cursor_shape = Qt.CursorShape.SizeFDiagCursor
        elif edge == EDGE_TOP_RIGHT or edge == EDGE_BOTTOM_LEFT:
            cursor_shape = Qt.CursorShape.SizeBDiagCursor
    
    if vk_instance.cursor().shape() != cursor_shape:
        vk_instance.setCursor(QCursor(cursor_shape))

def revert_button_flash(vk_instance, button, original_stylesheet):
    try:
        button.setStyleSheet(original_stylesheet) 
        key_name_found = None
        for name, btn_obj in vk_instance.buttons.items():
            if btn_obj == button:
                key_name_found = name
                break
        if key_name_found:
            vk_instance.update_single_key_label(key_name_found)
        else:
            print("Warning: Could not find key name for button flash revert. Updating all.")
            vk_instance.update_key_labels() 
    except Exception as e:
        print(f"Error reverting button flash: {e}")
        vk_instance.update_key_labels() 