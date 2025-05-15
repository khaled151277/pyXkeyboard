# PyXKeyboard Changelog

## Ver: 1.1.1 - (Current Date: e.g., 2025-04-17)

This release focuses on significant internal refactoring for better maintainability, performance improvements, and introduces a single-instance application behavior.

### ✨ New Features & Enhancements

*   **Single Instance Application:**
    *   Prevents multiple instances of PyXKeyboard from running simultaneously.
    *   Launching a new instance when one is already running will now activate and bring the existing instance's window to the foreground. (Implemented using `QLocalServer` and `QLocalSocket`).
*   **Improved System Tray Icon Handling:**
    *   The `QSystemTrayIcon` and its `QMenu` are now created only once.
    *   Subsequent updates to the tray (e.g., after settings changes or language switches) now refresh the menu content and icon status more efficiently, reducing object recreation and potential memory churn, especially when the main window is shown/hidden frequently.
*   **Optimized Key Label Updates:**
    *   The `update_key_labels_on_layout_change` function can now update a single key's label when specified, instead of re-processing all keys. This improves performance during actions like right-click shift (button flash).
*   **Optimized Focus Monitor Management:**
    *   Centralized logic for pausing and resuming the AT-SPI `EditableFocusMonitor` when dialogs (About, Settings) or the tray context menu are shown, reducing redundant start/stop operations.
*   **Language Button Display Logic:**
    *   The three dedicated "Lang" buttons now have a clearer display logic:
        *   `Lang2` (top-right on keyboard layout): Displays the **current** active system layout.
        *   `Lang1` (left of spacebar) & `Lang3` (right of spacebar): Both display the **next** layout in the system's configured cycle.
        *   Buttons will display "---" if the designated layout (e.g., "next" or "next+1") is not available (e.g., if only one or two layouts are configured in the system).

### 🐛 Bug Fixes

*   **Fixed `NameError` on Window Drag:** Resolved a `NameError: name 'QPushButton' is not defined` that occurred in `virtual_keyboard_gui.py` during mouse press events (specifically when trying to drag the window), which caused the application to crash. `QPushButton` is now correctly imported.
*   **Corrected Frameless Window Resize:** Fixed issues with frameless window resizing logic by correctly using defined edge constants (`EDGE_TOP`, `EDGE_LEFT`, etc.) instead of `Qt.Edge` enum values in bitwise operations within `mouseMoveEvent`.
*   **Fixed HTML Comments in f-strings:** Removed invalid HTML-style comments from f-strings in `vk_dialogs.py` that were causing `SyntaxError`.

### 🛠️ Code Refactoring & Internal Improvements

*   **Major Code Modularity:** The main `virtual_keyboard_gui.py` was significantly refactored into several smaller, more focused modules for improved organization and maintainability:
    *   `vk_ui.py`: UI element creation, styling, font, and geometry management.
    *   `vk_layout_handling.py`: XKB integration, layout file loading, and updating key labels based on current layout and modifiers.
    *   `vk_key_simulation.py`: XTEST key simulation logic and modifier state management related to simulation.
    *   `vk_auto_repeat.py`: Key auto-repeat functionality.
    *   `vk_dialogs.py`: "About" and "Settings" dialog interactions.
    *   `vk_tray_utils.py`: System tray icon and context menu management.
*   **Reduced Code Duplication:**
    *   Introduced helper function `_normalize_hex_color` in `vk_ui.py` to centralize hex color string validation.
    *   Refactored focus monitor pause/resume logic into helper methods in `VirtualKeyboard` class.
*   **Improved Layout File Loading:** Enhanced validation for custom JSON layout files.
*   **Version Synchronization:** Updated version number to 1.1.1 across all relevant files (source code, README, .desktop file, user guides).
*   **Documentation:**
    *   `README.md` and user guides (`user_guide.html`, `user_guide_ara.html`) updated to reflect new features and version.
    *   Added links in `README.md` to the new HTML documentation files (`CH_MAP_JSON_eng.html` and `CH_MAP_JSON_ara.html`) detailing the custom layout JSON format.

### 📝 Notes

*   The issue of high memory usage after prolonged use is still under observation. The refactoring and tray icon optimizations are expected to contribute positively, but further profiling might be needed if the issue persists significantly.
*   The "Show on all workspaces (Sticky)" option in settings remains non-functional.

---
*(Remember to replace `(Current Date: e.g., 2025-04-17)` with the actual release date.)*
