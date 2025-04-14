# -*- coding: utf-8 -*-
# Contains the SettingsDialog class for the settings/help window.

import os
import copy # For deepcopy
try:
    from PyQt6.QtWidgets import (
        QDialog, QTabWidget, QCheckBox, QVBoxLayout, QDialogButtonBox,
        QTextBrowser, QLabel, QFontComboBox, QSpinBox, QFormLayout, QSlider,
        QHBoxLayout, QColorDialog, QPushButton, QWidget, QComboBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QFont, QPalette, QColor
except ImportError:
    print("ERROR: PyQt6 library is required for SettingsDialog.")
    print("Please install it: pip install PyQt6")
    raise

from .settings_manager import DEFAULT_SETTINGS


class SettingsDialog(QDialog):
    """ Dialog window for application settings and help information. """
    settingsApplied = pyqtSignal(dict)

    def __init__(self, settings_data, current_font, is_focus_monitor_available: bool, parent=None):
        """ Initializes the dialog. """
        super().__init__(parent)
        self.original_settings_data = settings_data # Keep reference to original dict
        self.temp_settings = copy.deepcopy(settings_data) # Work on a copy
        self.is_focus_monitor_available = is_focus_monitor_available

        self.current_preview_font = QFont(current_font)
        self.current_preview_font.setFamily(self.temp_settings.get("font_family", DEFAULT_SETTINGS.get("font_family", "Sans Serif")))
        self.current_preview_font.setPointSize(self.temp_settings.get("font_size", DEFAULT_SETTINGS.get("font_size", 9)))

        self.setWindowTitle("Settings & Help")
        self.setMinimumSize(500, 650) # Increased height slightly more for new options

        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self.create_general_tab()
        self.create_appearance_tab()
        self.create_typing_tab()
        self.create_english_help_tab()
        self.create_arabic_help_tab()

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.apply_changes)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_help_file(self, browser_widget, filename, tab_title):
        """ Helper function to load HTML content from a file into a QTextBrowser. """
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            guide_file_path = os.path.join(script_dir, filename)

            if os.path.exists(guide_file_path):
                with open(guide_file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                browser_widget.setHtml(html_content)
            else:
                print(f"-> User guide file not found: {guide_file_path}")
                error_html = f"<html><body><h2>Error</h2><p>Could not find the user guide file (<code>{filename}</code>).</p></body></html>"
                browser_widget.setHtml(error_html)

        except Exception as e:
            print(f"-> ERROR loading user guide '{filename}': {e}")
            error_html = f"<html><body><h2>Error</h2><p>An error occurred while loading the user guide:</p><pre>{e}</pre></body></html>"
            browser_widget.setHtml(error_html)

    def create_general_tab(self):
        """ Creates the General settings tab using temp_settings. """
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        general_layout.setSpacing(15) # Increased spacing a bit

        self.remember_geometry_checkbox = QCheckBox("Remember window position and size on exit")
        remember = self.temp_settings.get("remember_geometry", DEFAULT_SETTINGS.get("remember_geometry", True))
        self.remember_geometry_checkbox.setChecked(remember)
        self.remember_geometry_checkbox.stateChanged.connect(self.on_remember_geometry_changed)
        general_layout.addWidget(self.remember_geometry_checkbox)

        self.always_on_top_checkbox = QCheckBox("Always on Top (Visible above other windows)")
        always_top = self.temp_settings.get("always_on_top", DEFAULT_SETTINGS.get("always_on_top", True))
        self.always_on_top_checkbox.setChecked(always_top)
        self.always_on_top_checkbox.setToolTip("Keeps the keyboard window above other application windows on the current workspace.")
        self.always_on_top_checkbox.stateChanged.connect(self.on_always_on_top_changed)
        general_layout.addWidget(self.always_on_top_checkbox)

        # --- تمت الإضافة: مربع اختيار الالتصاق ---
        self.sticky_checkbox = QCheckBox("Show on all workspaces (Sticky)")
        sticky = self.temp_settings.get("sticky_on_all_workspaces", DEFAULT_SETTINGS.get("sticky_on_all_workspaces", False))
        self.sticky_checkbox.setChecked(sticky)
        self.sticky_checkbox.setToolTip("Makes the keyboard visible on all virtual desktops/workspaces.\n(Requires Window Manager support - EWMH _NET_WM_STATE_STICKY)")
        self.sticky_checkbox.stateChanged.connect(self.on_sticky_changed)
        general_layout.addWidget(self.sticky_checkbox)
        # --- نهاية الإضافة ---


        self.auto_hide_checkbox = QCheckBox("Minimize window on middle mouse click")
        auto_hide = self.temp_settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True))
        self.auto_hide_checkbox.setChecked(auto_hide)
        self.auto_hide_checkbox.stateChanged.connect(self.on_auto_hide_changed)
        general_layout.addWidget(self.auto_hide_checkbox)

        self.auto_show_checkbox = QCheckBox("Auto-show keyboard when focusing an editable text field")
        auto_show = self.temp_settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
        self.auto_show_checkbox.setChecked(auto_show)
        self.auto_show_checkbox.setToolTip(
            "Requires Accessibility (AT-SPI) services to be running.\n"
            "May not work reliably in all environments (e.g., Wayland)."
        )
        self.auto_show_checkbox.setEnabled(self.is_focus_monitor_available)
        if not self.is_focus_monitor_available:
             self.auto_show_checkbox.setToolTip(self.auto_show_checkbox.toolTip() + "\n(Feature unavailable: Check dependencies)")
        self.auto_show_checkbox.stateChanged.connect(self.on_auto_show_changed)
        general_layout.addWidget(self.auto_show_checkbox)

        self.frameless_checkbox = QCheckBox("Frameless Window") # Removed restart hint
        frameless = self.temp_settings.get("frameless_window", DEFAULT_SETTINGS.get("frameless_window", False))
        self.frameless_checkbox.setChecked(frameless)
        self.frameless_checkbox.setToolTip("Removes the window title bar and borders.\nChanges take effect after clicking 'OK'.")
        self.frameless_checkbox.stateChanged.connect(self.on_frameless_changed)
        general_layout.addWidget(self.frameless_checkbox)

        general_layout.addStretch(1)
        self.tab_widget.addTab(general_tab, "General")

    def create_appearance_tab(self):
        """ Creates the Appearance settings tab using temp_settings. """
        appearance_tab = QWidget()
        appearance_layout = QFormLayout(appearance_tab)
        appearance_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        appearance_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(self.current_preview_font)
        self.font_combo.currentFontChanged.connect(self.on_font_family_changed)
        appearance_layout.addRow(QLabel("Font Family:"), self.font_combo)

        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(6, 36)
        self.size_spinbox.setSuffix(" pt")
        self.size_spinbox.setValue(self.current_preview_font.pointSize())
        self.size_spinbox.valueChanged.connect(self.on_font_size_changed)
        appearance_layout.addRow(QLabel("Font Size:"), self.size_spinbox)

        self.font_preview_label = QLabel("AaBbCc | أبجد هوز")
        self.font_preview_label.setFont(self.current_preview_font)
        initial_text_color_str = self.temp_settings.get("text_color", DEFAULT_SETTINGS.get("text_color", "#000000"))
        self.font_preview_label.setStyleSheet(f"color: {initial_text_color_str};")
        appearance_layout.addRow(QLabel("Font Preview:"), self.font_preview_label)

        text_color_label = QLabel("Text Color:")
        text_color_hbox = QHBoxLayout()
        self.text_color_button = QPushButton("Choose Color...")
        self.text_color_button.clicked.connect(self.on_text_color_button_clicked)
        text_color_hbox.addWidget(self.text_color_button)
        self.text_color_preview = QLabel()
        self.text_color_preview.setMinimumSize(40, 20)
        self.text_color_preview.setAutoFillBackground(True)
        self._update_text_color_preview(initial_text_color_str)
        text_color_hbox.addWidget(self.text_color_preview)
        text_color_hbox.addStretch(1)
        appearance_layout.addRow(text_color_label, text_color_hbox)

        opacity_label = QLabel("Background Opacity (Frameless Only):") # توضيح أنه للإطار بدون إطار
        opacity_hbox = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100) # 10% to 100%
        initial_opacity = self.temp_settings.get("window_opacity", DEFAULT_SETTINGS.get("window_opacity", 1.0))
        initial_slider_value = max(10, min(100, int(initial_opacity * 100)))
        self.opacity_slider.setValue(initial_slider_value)
        opacity_hbox.addWidget(self.opacity_slider)
        self.opacity_value_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_value_label.setMinimumWidth(40)
        opacity_hbox.addWidget(self.opacity_value_label)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        appearance_layout.addRow(opacity_label, opacity_hbox)

        button_style_label = QLabel("Button Style:")
        self.button_style_combo = QComboBox()
        self.button_styles = {"Default (Theme)": "default", "Flat": "flat", "Gradient (Basic)": "gradient"}
        self.button_style_combo.addItems(self.button_styles.keys())
        initial_style_name = self.temp_settings.get("button_style", DEFAULT_SETTINGS.get("button_style", "default"))
        initial_display_name = next((display for display, internal in self.button_styles.items() if internal == initial_style_name), "Default (Theme)")
        self.button_style_combo.setCurrentText(initial_display_name)
        self.button_style_combo.currentTextChanged.connect(self.on_button_style_changed)
        appearance_layout.addRow(button_style_label, self.button_style_combo)

        self.tab_widget.addTab(appearance_tab, "Appearance")

    def create_typing_tab(self):
        """ Creates the Typing settings tab including auto-repeat options. """
        typing_tab = QWidget()
        typing_layout = QFormLayout(typing_tab)
        typing_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        typing_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.auto_repeat_checkbox = QCheckBox("Enable key auto-repeat on long press")
        auto_repeat_enabled = self.temp_settings.get("auto_repeat_enabled", DEFAULT_SETTINGS.get("auto_repeat_enabled", True))
        self.auto_repeat_checkbox.setChecked(auto_repeat_enabled)
        self.auto_repeat_checkbox.stateChanged.connect(self.on_auto_repeat_enabled_changed)
        typing_layout.addRow(self.auto_repeat_checkbox)

        delay_label = QLabel("Initial Delay (before repeat starts):")
        delay_hbox = QHBoxLayout()
        self.repeat_delay_spinbox = QSpinBox()
        self.repeat_delay_spinbox.setRange(200, 3000); self.repeat_delay_spinbox.setSingleStep(50); self.repeat_delay_spinbox.setSuffix(" ms")
        initial_delay = self.temp_settings.get("auto_repeat_delay_ms", DEFAULT_SETTINGS.get("auto_repeat_delay_ms", 1500))
        self.repeat_delay_spinbox.setValue(initial_delay)
        self.repeat_delay_spinbox.valueChanged.connect(self.on_auto_repeat_delay_changed)
        delay_hbox.addWidget(self.repeat_delay_spinbox); delay_hbox.addStretch(1)
        typing_layout.addRow(delay_label, delay_hbox)

        interval_label = QLabel("Repeat Interval (speed):")
        interval_hbox = QHBoxLayout()
        self.repeat_interval_spinbox = QSpinBox()
        self.repeat_interval_spinbox.setRange(30, 500); self.repeat_interval_spinbox.setSingleStep(10); self.repeat_interval_spinbox.setSuffix(" ms")
        initial_interval = self.temp_settings.get("auto_repeat_interval_ms", DEFAULT_SETTINGS.get("auto_repeat_interval_ms", 100))
        self.repeat_interval_spinbox.setValue(initial_interval)
        self.repeat_interval_spinbox.valueChanged.connect(self.on_auto_repeat_interval_changed)
        interval_hbox.addWidget(self.repeat_interval_spinbox); interval_hbox.addStretch(1)
        typing_layout.addRow(interval_label, interval_hbox)

        self.repeat_delay_spinbox.setEnabled(auto_repeat_enabled); self.repeat_interval_spinbox.setEnabled(auto_repeat_enabled)
        delay_label.setEnabled(auto_repeat_enabled); interval_label.setEnabled(auto_repeat_enabled)

        self.tab_widget.addTab(typing_tab, "Typing")

    def create_english_help_tab(self):
        """ Creates the English Help tab. """
        help_tab_en = QWidget(); help_layout_en = QVBoxLayout(help_tab_en)
        help_browser_en = QTextBrowser(); help_browser_en.setOpenExternalLinks(True)
        help_layout_en.addWidget(help_browser_en)
        self._load_help_file(help_browser_en, "user_guide.html", "Help")
        self.tab_widget.addTab(help_tab_en, "Help")

    def create_arabic_help_tab(self):
        """ Creates the Arabic Help tab. """
        help_tab_ar = QWidget(); help_layout_ar = QVBoxLayout(help_tab_ar)
        help_browser_ar = QTextBrowser(); help_browser_ar.setOpenExternalLinks(True)
        help_layout_ar.addWidget(help_browser_ar)
        self._load_help_file(help_browser_ar, "user_guide_ara.html", "Arabic Help")
        self.tab_widget.addTab(help_tab_ar, "مساعدة عربية")

    # --- Signal Handlers (Update temp_settings only) ---

    def on_remember_geometry_changed(self, state):
        self.temp_settings["remember_geometry"] = (state == Qt.CheckState.Checked.value)

    def on_always_on_top_changed(self, state):
        self.temp_settings["always_on_top"] = (state == Qt.CheckState.Checked.value)

    # --- تمت الإضافة: معالج تغيير حالة الالتصاق ---
    def on_sticky_changed(self, state):
        self.temp_settings["sticky_on_all_workspaces"] = (state == Qt.CheckState.Checked.value)
    # --- نهاية الإضافة ---

    def on_auto_hide_changed(self, state):
        self.temp_settings["auto_hide_on_middle_click"] = (state == Qt.CheckState.Checked.value)

    def on_auto_show_changed(self, state):
        self.temp_settings["auto_show_on_edit"] = (state == Qt.CheckState.Checked.value)

    def on_frameless_changed(self, state):
        self.temp_settings["frameless_window"] = (state == Qt.CheckState.Checked.value)

    def on_font_family_changed(self, font):
        new_family = font.family()
        self.temp_settings["font_family"] = new_family
        self.current_preview_font.setFamily(new_family)
        self.font_preview_label.setFont(self.current_preview_font)

    def on_font_size_changed(self, size):
        self.temp_settings["font_size"] = size
        self.current_preview_font.setPointSize(size)
        self.font_preview_label.setFont(self.current_preview_font)

    def on_opacity_changed(self, value):
        opacity_float = value / 100.0
        self.temp_settings["window_opacity"] = opacity_float
        self.opacity_value_label.setText(f"{value}%")

    def on_text_color_button_clicked(self):
        current_color_str = self.temp_settings.get("text_color", DEFAULT_SETTINGS.get("text_color", "#000000"))
        initial_color = QColor(current_color_str)
        color = QColorDialog.getColor(initial_color, self, "Choose Text Color")
        if color.isValid():
            new_color_str = color.name()
            self.temp_settings["text_color"] = new_color_str
            self._update_text_color_preview(new_color_str)
            self.font_preview_label.setStyleSheet(f"color: {new_color_str};")

    def _update_text_color_preview(self, color_str):
        palette = self.text_color_preview.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(color_str))
        self.text_color_preview.setPalette(palette)

    def on_button_style_changed(self, display_name):
        internal_name = self.button_styles.get(display_name, "default")
        self.temp_settings["button_style"] = internal_name

    def on_auto_repeat_enabled_changed(self, state):
        """ Updates temp setting and enables/disables related controls. """
        is_enabled = (state == Qt.CheckState.Checked.value)
        self.temp_settings["auto_repeat_enabled"] = is_enabled
        # Enable/disable delay and interval controls
        self.repeat_delay_spinbox.setEnabled(is_enabled)
        self.repeat_interval_spinbox.setEnabled(is_enabled)
        typing_tab_layout = self.repeat_delay_spinbox.parentWidget().layout() # QFormLayout
        if typing_tab_layout:
             delay_label_widget = typing_tab_layout.labelForField(self.repeat_delay_spinbox.parentWidget())
             interval_label_widget = typing_tab_layout.labelForField(self.repeat_interval_spinbox.parentWidget())
             if delay_label_widget: delay_label_widget.setEnabled(is_enabled)
             if interval_label_widget: interval_label_widget.setEnabled(is_enabled)

    def on_auto_repeat_delay_changed(self, value_ms):
        """ Updates temp setting for repeat delay. """
        self.temp_settings["auto_repeat_delay_ms"] = value_ms

    def on_auto_repeat_interval_changed(self, value_ms):
        """ Updates temp setting for repeat interval. """
        self.temp_settings["auto_repeat_interval_ms"] = value_ms


    # --- Apply Changes ---
    def apply_changes(self):
        """ Copies changes from temp_settings to the original settings dictionary
            and emits a signal indicating that settings should be applied.
        """
        print("Applying settings from dialog...")
        # Update original dict directly - parent holds the single source of truth
        self.original_settings_data.update(self.temp_settings)
        # Emit the updated original dictionary
        self.settingsApplied.emit(self.original_settings_data)
        self.accept()
