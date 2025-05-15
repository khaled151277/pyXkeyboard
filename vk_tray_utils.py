# -*- coding: utf-8 -*-
# file: vk_tray_utils.py
# PyXKeyboard v1.0.7 - System Tray Utilities for VirtualKeyboard
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.

try:
    from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox
    from PyQt6.QtGui import QIcon, QAction, QActionGroup
    from PyQt6.QtCore import Qt, QTimer
except ImportError:
    print("ERROR: PyQt6 library is required for vk_tray_utils.")
    raise

from .settings_manager import DEFAULT_SETTINGS

def ensure_tray_icon_created(vk_instance):
    """Ensures the QSystemTrayIcon and its QMenu are created if they don't exist."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        if vk_instance.tray_icon: # If tray was previously available but now isn't
            vk_instance.tray_icon.hide()
            vk_instance.tray_icon.setContextMenu(None) # Clear context menu association
            vk_instance.tray_icon.deleteLater() # Schedule for deletion
            vk_instance.tray_icon = None
        if vk_instance.tray_menu:
            vk_instance.tray_menu.deleteLater()
            vk_instance.tray_menu = None
        print("System Tray not available.")
        return False

    if not vk_instance.tray_icon: # Create tray icon if it doesn't exist
        vk_instance.tray_icon = QSystemTrayIcon(vk_instance)
        vk_instance.tray_icon.activated.connect(vk_instance.tray_icon_activated)
        print("System tray icon created.")
    
    if not vk_instance.tray_menu: # Create context menu if it doesn't exist
        vk_instance.tray_menu = QMenu(vk_instance)
        vk_instance.tray_icon.setContextMenu(vk_instance.tray_menu)
        print("System tray menu created.")
    
    return True


def rebuild_tray_menu_content(vk_instance):
    """Clears and rebuilds the content of the tray menu."""
    if not vk_instance.tray_menu:
        return

    vk_instance.tray_menu.clear() # Clear existing actions

    # Reset language-specific menu items
    if vk_instance.language_menu:
        vk_instance.language_menu.deleteLater() # Delete the old QMenu object
        vk_instance.language_menu = None
    if vk_instance.lang_action_group:
        # QActionGroup is a QObject, let Qt handle its deletion when parent (vk_instance) is deleted
        # or explicitly delete if it's not parented correctly.
        # For simplicity, we'll re-create it.
        vk_instance.lang_action_group = None 
    vk_instance.language_actions = {}

    # Language selection submenu
    if vk_instance.xkb_manager:
        layouts = vk_instance.xkb_manager.get_available_layouts()
        if layouts and len(layouts) > 1: # Only show if multiple layouts
            vk_instance.language_menu = QMenu("Select Layout", vk_instance.tray_menu) # Parent to tray_menu
            vk_instance.lang_action_group = QActionGroup(vk_instance.language_menu) # Parent to language_menu
            vk_instance.lang_action_group.setExclusive(True)

            for lc_code in layouts:
                action = QAction(lc_code, vk_instance.language_menu, checkable=True)
                # Connect with a lambda that captures the current 'lc_code'
                action.triggered.connect(lambda checked=False, l=lc_code: vk_instance.set_system_language_from_menu(l))
                vk_instance.language_menu.addAction(action)
                vk_instance.language_actions[lc_code] = action
                vk_instance.lang_action_group.addAction(action)
            
            vk_instance.tray_menu.addMenu(vk_instance.language_menu)
            vk_instance.tray_menu.addSeparator()

    # Standard actions
    about_action = QAction("About...", vk_instance.tray_menu)
    about_action.triggered.connect(vk_instance.show_about_message)
    settings_action = QAction("Settings...", vk_instance.tray_menu)
    settings_action.triggered.connect(vk_instance.open_settings_dialog)
    vk_instance.tray_menu.addActions([about_action, settings_action])

    donate_action = QAction("Donate...", vk_instance.tray_menu)
    donate_action.triggered.connect(vk_instance._open_donate_link)
    vk_instance.tray_menu.addAction(donate_action)
    vk_instance.tray_menu.addSeparator()

    show_act = QAction("Show Keyboard", vk_instance.tray_menu)
    show_act.triggered.connect(vk_instance.show_normal_and_raise)
    
    hide_act_text = "Hide Keyboard" 
    if vk_instance.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True)):
         hide_act_text = "Hide (Middle Mouse Click)"
    hide_act = QAction(hide_act_text, vk_instance.tray_menu)
    # Enable/disable based on current setting, not just default
    hide_act.setEnabled(vk_instance.settings.get("auto_hide_on_middle_click", DEFAULT_SETTINGS.get("auto_hide_on_middle_click", True)))
    hide_act.triggered.connect(vk_instance.hide_to_tray)

    vk_instance.tray_menu.addActions([show_act, hide_act])
    vk_instance.tray_menu.addSeparator()

    quit_act = QAction("Quit", vk_instance.tray_menu)
    quit_act.triggered.connect(vk_instance.quit_application)
    vk_instance.tray_menu.addAction(quit_act)


def init_or_update_tray_icon(vk_instance):
    """
    Initializes the tray icon and menu if they don't exist,
    or updates the icon, menu content, and tooltip if they do.
    """
    if not ensure_tray_icon_created(vk_instance): # This creates tray_icon and tray_menu if needed
        return

    # Update the icon image if it has changed or not set
    try:
        if vk_instance.icon and (not vk_instance.tray_icon.icon().cacheKey() or vk_instance.tray_icon.icon().cacheKey() != vk_instance.icon.cacheKey()):
            vk_instance.tray_icon.setIcon(vk_instance.icon)
    except Exception as e:
        print(f"Error setting/updating tray icon image: {e}")

    rebuild_tray_menu_content(vk_instance) # Always rebuild menu content for freshness

    if not vk_instance.tray_icon.isVisible():
        try:
            vk_instance.tray_icon.show()
        except Exception as e: # Can happen on some DEs if tray disappears
            print(f"Error showing tray icon: {e}")
            if vk_instance.tray_icon: vk_instance.tray_icon.deleteLater(); vk_instance.tray_icon = None
            if vk_instance.tray_menu: vk_instance.tray_menu.deleteLater(); vk_instance.tray_menu = None
            return # Exit if showing fails critically

    update_tray_status_display(vk_instance) # Update tooltip and language check state


def update_tray_status_display(vk_instance):
    """Updates the tray icon's tooltip and the language menu's check state."""
    if not vk_instance.tray_icon or not vk_instance.tray_icon.isVisible():
        return

    tooltip_parts = [vk_instance.windowTitle()]
    if vk_instance.xkb_manager:
        current_layout = vk_instance.xkb_manager.get_current_layout_name()
        tooltip_parts.append(f"Layout: {current_layout or 'N/A'}")
    if not vk_instance.xlib_ok:
        tooltip_parts.append("Input SIM Error")
    
    auto_show_enabled = vk_instance.settings.get("auto_show_on_edit", DEFAULT_SETTINGS.get("auto_show_on_edit", False))
    if auto_show_enabled:
        tooltip_parts.append("AutoShow ON")
    if vk_instance.always_on_top:
        tooltip_parts.append("Always On Top")
    
    try:
        vk_instance.tray_icon.setToolTip("\n".join(tooltip_parts))
    except Exception as e:
        print(f"Error setting tray tooltip: {e}")

    update_tray_menu_language_check_state(vk_instance)


def tray_icon_activated(vk_instance, reason):
    """Handles activation of the tray icon (e.g., left-click)."""
    if reason == QSystemTrayIcon.ActivationReason.Trigger: # Typically left-click
        if vk_instance.isVisible() and not vk_instance.isMinimized():
            vk_instance.hide() # Or hide_to_tray() if preferred
        else:
            vk_instance.show_normal_and_raise()


def update_tray_menu_language_check_state(vk_instance): # Renamed from update_tray_menu_check_state
    """Updates the check state of the language actions in the tray menu."""
    if not vk_instance.xkb_manager or not vk_instance.lang_action_group or not vk_instance.language_actions:
        return

    current_internal_name = vk_instance.xkb_manager.get_current_layout_name()
    if not current_internal_name: # No current layout known
        return

    action_to_check = vk_instance.language_actions.get(current_internal_name)
    currently_checked_action_in_group = vk_instance.lang_action_group.checkedAction()

    if currently_checked_action_in_group and currently_checked_action_in_group != action_to_check:
        currently_checked_action_in_group.blockSignals(True)
        currently_checked_action_in_group.setChecked(False)
        currently_checked_action_in_group.blockSignals(False)
    
    if action_to_check and not action_to_check.isChecked():
        action_to_check.blockSignals(True)
        action_to_check.setChecked(True)
        action_to_check.blockSignals(False)


def hide_to_tray(vk_instance):
    """Hides the main window, showing a tray message if the tray icon is visible."""
    if vk_instance.tray_icon and vk_instance.tray_icon.isVisible():
        vk_instance.hide()
        try:
            message_icon = vk_instance.icon if vk_instance.icon else QIcon()
            vk_instance.tray_icon.showMessage(
                vk_instance.windowTitle(),
                "Minimized to system tray.",
                message_icon,
                2000 # milliseconds
            )
        except Exception as e:
            print(f"Tray icon message display failed: {e}")
    elif not vk_instance.is_frameless: # Has window controls
        print("No system tray, minimizing window instead.")
        vk_instance.showMinimized()
    else: # Frameless and no tray
        print("No system tray and frameless, hiding window.")
        vk_instance.hide()