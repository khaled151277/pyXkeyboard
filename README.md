# pyxkeyboard v1.0.5

A simple, customizable OSK on-screen virtual keyboard for Linux systems (primarily X11/Xorg), featuring layout switching, key simulation via XTEST, and optional auto-show functionality using AT-SPI.

![Screenshot](placeholder.png)
*(Suggestion: Replace placeholder.png with an actual screenshot)*

## Key Features

*   **On-Screen Typing:** Click keys to simulate input into other applications (using XTEST).
*   **System Layout Switching:** Easily switch between configured system keyboard layouts (e.g., English, Arabic) using the `Lang` button or the system tray menu (uses `xkb-switch` if available, otherwise `setxkbmap`).
*   **Visual Layout Display:** Keyboard display automatically reflects the currently active system layout (loads characters from corresponding layout files like `layouts/us.json`, `layouts/ar.json`).
*   **Modifier Keys:** Functional `Shift`, `Ctrl`, `Alt`, and `Caps Lock` keys. Shift, Ctrl, and Alt act as "sticky keys" for the next non-modifier key press. `Win`/`Super` keys act as single-press keys.
*   **Right-Click Shift:** Right-click character keys to simulate `Shift + Key`.
*   **Movable:** Drag the window background using the **left mouse button** to reposition (works whether frameless or framed).
*   **Always on Top:** Option to keep the keyboard window visible above other application windows (Default: On).
*   **System Tray Integration:** Minimize to tray, select layout, show keyboard, and quit from the tray menu (uses a keyboard icon).
*   **Key Auto-Repeat:** Enable/disable key repeat on long press (includes arrow keys, backspace, delete, space, tab, enter, letters, numbers, symbols) and configure initial delay and repeat interval.
*   **Customizable Appearance:**
    *   Adjust font family and size (Default: Noto Naskh Arabic 10pt).
    *   Set button text color.
    *   Optionally use **system theme colors** for window and button backgrounds (Default: On). If enabled, custom background color and button style settings are ignored, but the set text color is still used.
    *   If *not* using system colors:
        *   Set custom window background color.
        *   Set custom button background color (mainly affects "Flat" style).
        *   Choose button style (Default, Flat, Gradient).
    *   Set window background **opacity** (works for both framed and frameless windows, compositor support required, Default: 0.9).
*   **Configurable Behavior:**
    *   **Frameless Window:** Option to remove the window title bar and borders (Default: On).
    *   Remember window position and size.
    *   Optional middle-click on background to hide to tray.
    *   **Auto-show when editing text:** Automatically shows the keyboard when focus enters an editable text field (requires AT-SPI accessibility services).
    *   **Show on all workspaces (Sticky):** _[Option available but Not Currently Functional]_

![Settings Screenshot](placeholder2.png)
*(Suggestion: Replace placeholder2.png with a screenshot of the settings window)*

## System Requirements

*   **Operating System:** **Linux** (Designed and tested primarily on **X11/Xorg** sessions).
    *   *Note:* Key simulation (XTEST), system layout switching (XKB), focus monitoring (AT-SPI), and window manager hints (Always on Top, Sticky) may have limited or no functionality on Wayland sessions.
*   **Python:** Python 3.x

## Installation & Dependencies

**1. Dependencies:**

Ensure the following packages are installed on your Debian/Ubuntu-based system. Use your distribution's package manager for equivalents on other systems.

![Dependencies Screenshot](placeholder3.png)
*(Suggestion: Replace placeholder3.png with a relevant image if desired)*

*   **Required:**
    ```bash
    sudo apt update
    sudo apt install python3 python3-pyqt6 python3-xlib x11-xkb-utils
    ```
    *(Provides: Python interpreter, Core GUI, Key simulation, Layout switching command)*

*   **Recommended (for Optional Features):**
    ```bash
    # For Auto-Show feature:
    sudo apt install python3-gi gir1.2-atspi-2.0

    # For default font:
    sudo apt install fonts-noto-naskh-arabic
    ```
    *Note: The Auto-Show feature also requires **Accessibility Services (AT-SPI Bus)** to be enabled in your Desktop Environment settings (check Accessibility/Universal Access). You might need to log out and log back in after enabling it.*

**2. Installation (using DEB package):**

This is the recommended installation method for end-users on Debian/Ubuntu-based systems.

1.  **Download:** Obtain the `pyxkeyboard_*.deb` file for the latest release.
2.  **Install:** Open a terminal in the directory where you downloaded the file and run:
    ```bash
    sudo dpkg -i pyxkeyboard_*.deb
    ```
    *(Replace `*` with the actual version/architecture)*
3.  **Fix Dependencies (If necessary):** If `dpkg` reports missing dependencies that weren't installed in Step 1, run:
    ```bash
    sudo apt --fix-broken install
    ```
4.  **Update Caches (Important!):** To ensure the application icon and menu entry appear correctly, run:
    ```bash
    sudo gtk-update-icon-cache /usr/share/icons/hicolor/
    sudo update-desktop-database
    ```
5.  **Log Out/In:** Log out of your desktop session and log back in for the menu/icon changes to take full effect.

You should now find "PyXKeyboard" in your application menu.

**To Uninstall:**
```bash
sudo apt remove pyxkeyboard
```

**(Alternative) Running Directly:**
For development or testing without installation:
```bash
# Clone the repository first if you haven't already
# git clone https://github.com/khaled151277/pyxkeyboard.git
# cd pyxkeyboard
# From the project root directory:
python3 -m pyxkeyboard.main
```

## How to Use

1.  **Starting:** Launch "PyXKeyboard" from your application menu or run `pyxkeyboard` in the terminal.
2.  **Typing:** Open your target application, then click keys on the virtual keyboard.
3.  **Modifiers:** Click `Shift`, `Ctrl`, or `Alt` once to activate for the next key. Click `Caps Lock` to toggle. Right-click character keys for Shift+Key. `Win`/`Super` keys act as single presses.
4.  **Arrow Keys & Repeat:** Click arrow keys or other repeatable keys. Long-press triggers auto-repeat if enabled.
5.  **Switching Layouts:** Use the `Lang` button to cycle or right-click the tray icon -> "Select Layout". The display updates based on `.json` files in the installation's `layouts` directory.
6.  **Moving:** Left-click and drag the background area.
7.  **Minimizing / Hiding:** Use window controls, the custom `_` button (if frameless), or middle-click the background (if enabled).
8.  **Showing from Tray:** Left-click the tray icon or use the right-click menu.
9.  **Settings (<code>Set</code> button):** Configure appearance and behavior (500x500 window). Note that "Use system theme colors" overrides custom backgrounds and button style, but respects the custom text color setting.
10. **Quitting:** Use the custom `X` button (if frameless), the tray menu, or the standard window close button (if framed and no tray).

## Troubleshooting

*   **Typing doesn't work / wrong characters:** Check XTEST status in "About". Ensure `python-xlib` installed, you're on X11. Wrong characters usually mean system layout differs from keyboard's visual layout (e.g., system AZERTY vs visual QWERTY).
*   **Correct language characters not displayed:** Ensure a `.json` file matching your system layout code (e.g., `ara.json`) exists in `/usr/lib/python*/site-packages/pyxkeyboard/layouts/`. Check logs for loading errors.
*   **Language switching fails:** Check XKB status in "About". Ensure `xkb-switch` or `setxkbmap` is installed. Configure multiple layouts in OS settings.
*   **Tray icon missing:** Your desktop might lack tray support.
*   **Middle-click hide fails:** Check the setting in General tab.
*   **Auto-Show fails:** Check setting, ensure AT-SPI dependencies installed AND Accessibility Services are **enabled** in desktop settings (may require logout/login). Check AT-SPI status in "About".
*   **Always on Top fails:** Check setting. Depends on Window Manager support.
*   **"Sticky" option:** Not functional currently.
*   **Appearance issues:** Opacity/colors depend on compositor. If using system colors, ensure your chosen text color contrasts well with your theme.
*   **Generic Application Icon:** Run `sudo gtk-update-icon-cache /usr/share/icons/hicolor/ && sudo update-desktop-database` then **log out and log back in**.
*   **Settings issues:** Check permissions for `~/.pyxkeyboard`. Delete `settings.json` inside to reset.

## About

*   **Version:** 1.0.5
*   **Developer:** Khaled Abdelhamid
*   **Contact:** khaled1512@gmail.com
*   **License:** GPL-3.0
*   **Support:** PayPal: [paypal.me/kh1512](https://paypal.me/kh1512) (<code>paypal.me/kh1512</code>)
