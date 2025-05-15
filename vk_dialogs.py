# -*- coding: utf-8 -*-
# file: vk_dialogs.py
# PyXKeyboard v1.0.7 - Dialog Management for VirtualKeyboard
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

import os
import copy
import webbrowser
from pathlib import Path

try:
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import QTimer, Qt
except ImportError:
    print("ERROR: PyQt6 library is required for vk_dialogs.")
    raise

from .settings_dialog import SettingsDialog
from .settings_manager import DEFAULT_SETTINGS
from .XKB_Switcher import XKBManager # For status in About dialog


def show_about_message(vk_instance):
    """Displays the About dialog box."""
    program_name = vk_instance.windowTitle()
    monitor_was_running_before_dialog = vk_instance._pause_focus_monitor_if_running()

    try:
        status_xkb = "N/A"
        xkb_method_info = f" ({vk_instance.xkb_manager.get_current_method()})" if vk_instance.xkb_manager else ""
        if XKBManager is None: 
            status_xkb = "Disabled (XKB_Switcher module missing)"
        elif vk_instance.xkb_manager:
            layouts_str = ', '.join(vk_instance.xkb_manager.get_available_layouts() or ['N/A'])
            status_xkb = f"Enabled{xkb_method_info} (Layouts: {layouts_str})"
        else:
            status_xkb = "Disabled (Initialization error)"

        status_xtest = "N/A"
        if vk_instance.is_xlib_dummy:
            status_xtest = "Disabled (python-xlib missing or failed)"
        elif vk_instance.xlib_ok: 
            status_xtest = "Enabled"
        else:
            status_xtest = "Disabled (Initialization error or XTEST unavailable)"
        
        status_auto_show = "N/A"
        if not vk_instance.focus_monitor_available:
            status_auto_show = "Disabled (AT-SPI Focus Monitor unavailable - check dependencies)"
        else:
            setting_enabled = vk_instance.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
            if vk_instance.focus_monitor and setting_enabled:
                is_currently_active_for_status = monitor_was_running_before_dialog or \
                                                 (vk_instance.focus_monitor and vk_instance.focus_monitor.is_running())
                status_auto_show = "Enabled (Active)" if is_currently_active_for_status else "Enabled (Inactive)"
            elif setting_enabled: 
                status_auto_show = "Enabled (Inactive - Initialization Failed?)"
            else: 
                status_auto_show = "Disabled (in Settings)"


        script_dir = os.path.dirname(os.path.abspath(__file__)) 
        badge_icon_path_relative = os.path.join('icons', 'icon_64.png') 
        badge_icon_path_full = os.path.join(script_dir, badge_icon_path_relative)
        badge_html = ""
        if os.path.exists(badge_icon_path_full):
            try:
                badge_uri = Path(badge_icon_path_full).as_uri()
                badge_html = f'<img src="{badge_uri}" alt="App Icon" width="64" height="64" style="float: left; margin-right: 10px; margin-bottom: 10px;">'
            except Exception as uri_e:
                print(f"Error creating file URI for badge icon: {uri_e}")
                badge_html = f'<img src="{badge_icon_path_relative}" alt="Icon" width="64" height="64" style="float: left; margin-right: 10px; margin-bottom: 10px;">'
        else:
            print(f"Badge icon not found at: {badge_icon_path_full}")


        version_str = "N/A"
        ver_file_path = os.path.join(script_dir, "ver.txt")
        if os.path.exists(ver_file_path):
            try:
                with open(ver_file_path, 'r') as vf:
                    version_str = vf.read().strip()
            except Exception as e_ver:
                print(f"Error reading version file: {e_ver}")


        main_info = f"""
            {badge_html}
            <div style="overflow: hidden;"> 
            <p><b>{program_name} v{version_str}</b><br>
            A simple on-screen virtual keyboard for Linux.</p>
            <p>Developed by: Khaled Abdelhamid<br>
            Contact: <a href="mailto:khaled1512@gmail.com">khaled1512@gmail.com</a></p>
            <p><b>License:</b><br>GNU General Public License v3 (GPLv3)</p>
            <p><b>Disclaimer:</b><br>Provided 'as is'. Use at your own risk.</p>
            <p>Support development via PayPal:<br>
            <a href="https://paypal.me/kh1512">https://paypal.me/kh1512</a><br>
            (Copy: <code>paypal.me/kh1512</code>)</p>
            <p>Thank you!</p>
            </div>
            <div style="clear: both;"></div>
            """

        full_message = main_info + "<hr>" + \
                       f"""<p><b>Status:</b><br>
                       Layout Control (XKB): {status_xkb}<br>
                       Input Simulation (XTEST): {status_xtest}<br>
                       Auto-Show (AT-SPI): {status_auto_show}</p>
                       """

        QMessageBox.information(vk_instance, f"About {program_name}", full_message)

    finally:
        vk_instance._resume_focus_monitor_if_needed(monitor_was_running_before_dialog)
        vk_instance._update_tray_status_display() # تحديث حالة الـ tray بدلاً من إعادة بنائه بالكامل


def open_settings_dialog(vk_instance):
    settings_copy = copy.deepcopy(vk_instance.settings)
    dialog = SettingsDialog(settings_copy, vk_instance.app_font, vk_instance.focus_monitor_available, vk_instance)
    dialog.settingsApplied.connect(vk_instance._apply_settings_from_dialog)

    monitor_was_running_before_dialog = vk_instance._pause_focus_monitor_if_running()
    try:
        dialog.exec() 
    finally:
        vk_instance._resume_focus_monitor_if_needed(monitor_was_running_before_dialog)
        # init_tray_icon هنا قد يكون ضروريًا إذا كانت الإعدادات تؤثر على هيكل القائمة
        # لكن _apply_settings_from_dialog تستدعي init_tray_icon بالفعل
        # لذا، قد لا نحتاج لاستدعاء إضافي هنا، أو نكتفي بتحديث الحالة.
        vk_instance._update_tray_status_display() # يكفي لتحديث التلميح وحالة اللغة
        
        try:
            dialog.settingsApplied.disconnect(vk_instance._apply_settings_from_dialog)
        except (TypeError, RuntimeError): 
            pass

def open_donate_link(vk_instance):
    url = "https://paypal.me/kh1512"
    print(f"Opening donation link: {url}")
    try:
        webbrowser.open_new_tab(url)
    except Exception as e:
        print(f"ERROR opening donation link: {e}")
        QMessageBox.warning(vk_instance, "Link Error",
                            f"Could not open donation link:\n{url}\n\nError: {e}")