# -*- coding: utf-8 -*-
# File: XKB_Switcher.py
# PyXKeyboard v1.0.5 - A simple, customizable on-screen virtual keyboard.
# Features include X11 key simulation (XTEST), system layout switching (XKB),
# visual layout updates, configurable appearance (fonts, colors, opacity, styles),
# auto-repeat, system tray integration, and optional AT-SPI based auto-show.
# Developed by Khaled Abdelhamid (khaled1512@gmail.com) - Licensed under GPLv3.
# Manages keyboard layouts using 'xkb-switch' if available, falling back to 'setxkbmap'xkb-switch.

import subprocess
import re
import os
import sys # For stderr
import shutil # To check for command existence
import threading # For monitoring thread
import time
from typing import List, Optional, Tuple

# --- *** إضافة: استيراد من PyQt لتسهيل الإشارات *** ---
# هذا يضيف اعتمادية PyQt6 على هذا الملف، لكنه يبسط إرسال الإشارات
try:
    from PyQt6.QtCore import QObject, pyqtSignal
except ImportError:
    # Fallback if PyQt6 is not available (monitoring won't signal GUI)
    print("WARNING: PyQt6 not found in XKB_Switcher. GUI won't be notified of layout changes via xkb-switch monitor.")
    QObject = object # Dummy QObject
    pyqtSignal = lambda *args, **kwargs: None # Dummy signal
# --- *** نهاية الإضافة *** ---


class XKBManagerError(Exception):
    """ Custom exception for errors within XKBManager. """
    pass

# --- *** تعديل: إضافة QObject للإشارات *** ---
class XKBManager(QObject):
    """
    Manages keyboard layouts using 'xkb-switch' if available, falling back
    to the 'setxkbmap' command-line tool on Linux/X11.
    Allows querying available layouts, getting the current layout,
    setting layouts by index or name, cycling, and optionally monitoring changes.
    """
    # Signal emitted when layout changes (detected by monitor or refresh)
    # Passes the new layout name (str)
    layoutChanged = pyqtSignal(str)
# --- *** نهاية التعديل *** ---

    METHOD_XKB_SWITCH = 'xkb-switch'
    METHOD_SETXKBMAP = 'setxkbmap'
    METHOD_NONE = 'none'

    def __init__(self, auto_refresh: bool = True, start_monitoring: bool = False):
        """
        Initializes the XKBManager.

        Args:
            auto_refresh (bool): If True, automatically fetches the available
                                 layouts and attempts to determine the initial
                                 system layout upon initialization. Defaults to True.
            start_monitoring (bool): If True, attempts to start the monitoring
                                     thread using 'xkb-switch -W' if available.
                                     Requires the main application event loop
                                     to be running. Defaults to False.
        """
        # --- *** تعديل: استدعاء مُنشئ QObject *** ---
        super().__init__() # Needed for signals
        # --- *** نهاية التعديل *** ---

        self._method = self.METHOD_NONE
        self._available_layouts: List[str] = []
        self._current_layout_index: int = -1
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_process: Optional[subprocess.Popen] = None
        self._monitoring_active = False
        self._stop_monitor_event = threading.Event()

        # --- تحديد الطريقة المستخدمة ---
        self._xkb_switch_path = shutil.which('xkb-switch')
        if self._xkb_switch_path:
            print(f"Found xkb-switch at: {self._xkb_switch_path}")
            # Try using xkb-switch first
            if self._initialize_with_xkb_switch():
                self._method = self.METHOD_XKB_SWITCH
                print("XKBManager: Initialized using xkb-switch.")
            else:
                print("XKBManager: Failed to initialize with xkb-switch, falling back to setxkbmap.")
                if self._initialize_with_setxkbmap():
                    self._method = self.METHOD_SETXKBMAP
                    print("XKBManager: Initialized using setxkbmap.")
                else:
                    print("XKBManager: ERROR - Failed to initialize with setxkbmap as well.", file=sys.stderr)
                    self._method = self.METHOD_NONE
        else:
            print("XKBManager: xkb-switch not found in PATH.")
            if self._initialize_with_setxkbmap():
                self._method = self.METHOD_SETXKBMAP
                print("XKBManager: Initialized using setxkbmap.")
            else:
                print("XKBManager: ERROR - Failed to initialize with setxkbmap.", file=sys.stderr)
                self._method = self.METHOD_NONE
        # --- نهاية تحديد الطريقة ---

        # --- بدء المراقبة إذا طُلب وكان ممكنا ---
        if start_monitoring and self.can_monitor():
            self.start_change_monitor()
        # --- نهاية بدء المراقبة ---

    # --- *** تعديل: دالة تهيئة جديدة لـ xkb-switch *** ---
    def _initialize_with_xkb_switch(self) -> bool:
        """Attempts to initialize available layouts and current index using xkb-switch."""
        layouts_output = self._run_command([self._xkb_switch_path, '-l'], timeout=0.5)
        current_output = self._run_command([self._xkb_switch_path], timeout=0.5)

        if layouts_output is None or current_output is None:
            print("xkb-switch initialization failed: command error.")
            return False

        self._available_layouts = [line for line in layouts_output.splitlines() if line.strip()]
        if not self._available_layouts:
            print("xkb-switch initialization failed: no layouts returned by '-l'.")
            return False

        current_layout_name = current_output.strip()
        if current_layout_name in self._available_layouts:
            try:
                self._current_layout_index = self._available_layouts.index(current_layout_name)
                print(f"xkb-switch: Initial layout '{current_layout_name}', index: {self._current_layout_index}")
                return True
            except ValueError:
                # Should not happen if it's in the list, but handle anyway
                print(f"xkb-switch initialization warning: current layout '{current_layout_name}' in list but index failed?", file=sys.stderr)
                self._current_layout_index = 0
                return True # Still consider it initialized
        else:
            print(f"xkb-switch initialization warning: current layout '{current_layout_name}' not in available list {self._available_layouts}. Defaulting to index 0.", file=sys.stderr)
            self._current_layout_index = 0
            return True # Consider initialized even if current is odd
    # --- *** نهاية الدالة *** ---

    # --- *** تعديل: دالة تهيئة جديدة لـ setxkbmap *** ---
    def _initialize_with_setxkbmap(self) -> bool:
        """Attempts to initialize available layouts and current index using setxkbmap."""
        query_output = self._run_command(['setxkbmap', '-query'], timeout=0.5)
        if query_output is None:
            print("setxkbmap initialization failed: query command error.")
            return False

        layout_match = re.search(r'layout:\s*([\w,]+)', query_output)
        if layout_match:
            self._available_layouts = layout_match.group(1).split(',')
        else:
            print("setxkbmap initialization warning: Could not parse 'layout:' line. Assuming 'us'.", file=sys.stderr)
            # Fallback if layout line isn't present (might happen in minimal setups)
            self._available_layouts = ['us'] # Default assumption

        if not self._available_layouts:
             print("setxkbmap initialization failed: No layouts found in query.", file=sys.stderr)
             return False

        # Try to parse the *first* layout as the current one from the query itself
        current_layout_name = self._available_layouts[0] # Assume first is current

        if current_layout_name in self._available_layouts: # Should always be true here
            self._current_layout_index = self._available_layouts.index(current_layout_name) # Will be 0
            print(f"setxkbmap: Initial layout '{current_layout_name}', index: {self._current_layout_index}")
            return True
        else: # Should be unreachable, but for safety
             print(f"setxkbmap initialization error: Parsed layout '{current_layout_name}' not in list?", file=sys.stderr)
             self._current_layout_index = 0
             return True
    # --- *** نهاية الدالة *** ---

    def get_current_method(self) -> str:
        """Returns the method being used ('xkb-switch', 'setxkbmap', or 'none')."""
        return self._method

    def _run_command(self, command_list: List[str], timeout: float = 1.0, capture=True) -> Optional[str]:
        """ Runs an external command. """
        try:
            env = os.environ.copy()
            # Use Popen for more control if not capturing output or needing process handle
            if not capture:
                 process = subprocess.Popen(command_list, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 # Caller needs to handle the process object
                 return process # Return the process handle directly

            result = subprocess.run(
                command_list,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
                env=env
            )
            return result.stdout.strip()
        except FileNotFoundError:
            # Distinguish between xkb-switch not found and setxkbmap not found
            cmd_name = command_list[0]
            if cmd_name == 'xkb-switch' and self._xkb_switch_path is None:
                # This was expected if we fell back to setxkbmap
                pass # Don't raise an error here, handled during init
            else:
                # If setxkbmap is not found, or xkb-switch was expected but missing now
                raise XKBManagerError(f"Command not found: '{cmd_name}'. Is it installed and in PATH?")
            return None
        except subprocess.CalledProcessError as e:
            # print(f"WARNING: Command '{' '.join(command_list)}' failed with code {e.returncode}. Stderr: {e.stderr.strip()}", file=sys.stderr)
            return None
        except subprocess.TimeoutExpired:
            print(f"WARNING: Command '{' '.join(command_list)}' timed out after {timeout} seconds.", file=sys.stderr)
            return None
        except Exception as e:
            print(f"WARNING: Unexpected error running {' '.join(command_list)}: {e}", file=sys.stderr)
            return None

    # --- *** تعديل: استخدام الطريقة المحددة *** ---
    def refresh(self) -> bool:
        """Refreshes the internal list of available layouts."""
        print(f"Refreshing layout list using {self._method}...")
        new_layouts = []
        success = False

        if self._method == self.METHOD_XKB_SWITCH:
            output = self._run_command([self._xkb_switch_path, '-l'])
            if output is not None:
                new_layouts = [line for line in output.splitlines() if line.strip()]
                success = True
            else:
                print("ERROR: xkb-switch -l failed during refresh.", file=sys.stderr)
        elif self._method == self.METHOD_SETXKBMAP:
            output = self._run_command(['setxkbmap', '-query'])
            if output is not None:
                layout_match = re.search(r'layout:\s*([\w,]+)', output)
                if layout_match:
                    new_layouts = layout_match.group(1).split(',')
                    success = True
                else:
                    print("ERROR: Could not parse 'layout:' line from setxkbmap query during refresh.", file=sys.stderr)
            else:
                print("ERROR: setxkbmap -query failed during refresh.", file=sys.stderr)
        else:
            print("ERROR: Cannot refresh, no valid method initialized.", file=sys.stderr)
            return False

        if not success or not new_layouts:
            print("Layout refresh failed.")
            return False

        # --- Update internal state ---
        if set(new_layouts) != set(self._available_layouts):
            print(f"Available layout set updated: {self._available_layouts} -> {new_layouts}")
            self._available_layouts = new_layouts
            # Re-validate index after list change
            current_name = self.get_current_layout_name() # Get current name based on *internal* state
            if current_name and current_name in self._available_layouts:
                try:
                    self._current_layout_index = self._available_layouts.index(current_name)
                except ValueError:
                     self._current_layout_index = 0 # Fallback
            else:
                # If previous name is gone or invalid, try querying system again
                queried_name = self.query_current_layout_name()
                if queried_name and queried_name in self._available_layouts:
                    try:
                        self._current_layout_index = self._available_layouts.index(queried_name)
                        print(f"  -> Re-synced index to system layout: {queried_name} ({self._current_layout_index})")
                    except ValueError:
                        self._current_layout_index = 0
                else:
                     self._current_layout_index = 0 if self._available_layouts else -1 # Fallback

        # --- Final Sanity Check ---
        if not self._available_layouts: self._current_layout_index = -1
        elif not (0 <= self._current_layout_index < len(self._available_layouts)):
            print(f"WARNING: Current layout index {self._current_layout_index} invalid after refresh, resetting to 0.", file=sys.stderr)
            self._current_layout_index = 0

        print(f"Refresh successful. Current index: {self._current_layout_index}, Layout: {self.get_current_layout_name()}")
        return True
    # --- *** نهاية التعديل *** ---


    # --- *** تعديل: استخدام الطريقة المحددة *** ---
    def query_current_layout_name(self) -> Optional[str]:
        """Queries the system and returns the currently active layout name."""
        if self._method == self.METHOD_XKB_SWITCH:
            output = self._run_command([self._xkb_switch_path])
            return output.strip() if output else None
        elif self._method == self.METHOD_SETXKBMAP:
            output = self._run_command(['setxkbmap', '-query'])
            if output:
                layout_match = re.search(r'layout:\s*([\w,]+)', output)
                if layout_match:
                    layouts = layout_match.group(1).split(',')
                    return layouts[0] if layouts else None
            return None
        else:
            return None # No method available
    # --- *** نهاية التعديل *** ---

    def get_available_layouts(self) -> List[str]:
        """Returns the cached list of available layout names."""
        return self._available_layouts

    def get_current_layout_index(self) -> int:
        """Returns the index the manager *believes* is currently active."""
        if not self._available_layouts: return -1
        if not (0 <= self._current_layout_index < len(self._available_layouts)): return 0
        return self._current_layout_index

    def get_current_layout_name(self) -> Optional[str]:
        """Returns the name of the layout the manager *believes* is active."""
        index = self.get_current_layout_index()
        if 0 <= index < len(self._available_layouts):
            return self._available_layouts[index]
        return None

    def _set_internal_index(self, index: int, emit_signal: bool = True):
        """ Safely sets the internal current layout index and optionally emits signal. """
        if 0 <= index < len(self._available_layouts):
            if self._current_layout_index != index:
                 old_name = self.get_current_layout_name()
                 self._current_layout_index = index
                 new_name = self.get_current_layout_name()
                 print(f"Internal index updated: {index} ({old_name} -> {new_name})")
                 if emit_signal and new_name:
                     self.layoutChanged.emit(new_name) # Emit signal with new name
        elif len(self._available_layouts) > 0:
            if self._current_layout_index != 0:
                print(f"WARNING: Attempted to set invalid internal index {index}. Setting to 0.", file=sys.stderr)
                old_name = self.get_current_layout_name()
                self._current_layout_index = 0
                new_name = self.get_current_layout_name()
                if emit_signal and new_name:
                     self.layoutChanged.emit(new_name)
        else:
             self._current_layout_index = -1

    # --- *** تعديل: استخدام الطريقة المحددة *** ---
    def set_layout_by_index(self, index: int, update_system: bool = True) -> bool:
        """Attempts to set the active layout to the one at the specified index."""
        if not (0 <= index < len(self._available_layouts)):
            print(f"ERROR: Invalid layout index {index} requested. Available: {len(self._available_layouts)} layouts.", file=sys.stderr)
            return False

        target_layout = self._available_layouts[index]
        success = False

        if update_system:
            print(f"Attempting to set system layout to index {index} ('{target_layout}') using {self._method}...")
            if self._method == self.METHOD_XKB_SWITCH:
                command = [self._xkb_switch_path, '-s', target_layout]
                if self._run_command(command) is not None:
                    print(f"xkb-switch -s {target_layout} likely succeeded.")
                    success = True
                else:
                    print(f"ERROR: xkb-switch -s {target_layout} failed.", file=sys.stderr)

            elif self._method == self.METHOD_SETXKBMAP:
                reordered_layouts = [target_layout] + [l for i, l in enumerate(self._available_layouts) if i != index]
                layout_string = ",".join(reordered_layouts)
                command = ['setxkbmap', '-layout', layout_string]
                if self._run_command(command) is not None:
                    print(f"setxkbmap -layout {layout_string} likely succeeded.")
                    success = True
                else:
                    print(f"ERROR: setxkbmap -layout {layout_string} failed.", file=sys.stderr)
            else:
                 print("ERROR: Cannot set layout, no valid method.", file=sys.stderr)
                 return False
        else:
            success = True # Only updating internal state

        if success:
            self._set_internal_index(index, emit_signal=update_system) # Emit only if system was updated

        return success
    # --- *** نهاية التعديل *** ---

    def set_layout_by_name(self, name: str, update_system: bool = True) -> bool:
        """Attempts to set the active layout to the one matching the given name."""
        try:
            index = self._available_layouts.index(name)
            return self.set_layout_by_index(index, update_system=update_system)
        except ValueError:
            print(f"ERROR: Layout name '{name}' not found in available layouts: {self._available_layouts}", file=sys.stderr)
            return False
        except Exception as e:
             print(f"ERROR finding index for layout name '{name}': {e}", file=sys.stderr)
             return False

    # --- *** تعديل: استخدام الطريقة المحددة *** ---
    def cycle_next_layout(self) -> bool:
        """Attempts to switch the *system* layout to the next one."""
        num_layouts = len(self._available_layouts)
        if num_layouts <= 1:
            print("Not enough layouts configured in the system to cycle.")
            return False

        success = False
        if self._method == self.METHOD_XKB_SWITCH:
            print("Cycling layout using xkb-switch -n...")
            command = [self._xkb_switch_path, '-n']
            # We run the command, but the *real* update comes from monitoring or next query
            if self._run_command(command) is not None:
                 print("xkb-switch -n command likely succeeded.")
                 # Don't update index immediately, wait for monitor or next refresh/query
                 # We *could* calculate the next index, but let's rely on querying/monitoring
                 # If monitoring isn't active, the change will be picked up by the timer in GUI
                 success = True # Assume command worked
            else:
                 print("ERROR: xkb-switch -n failed.", file=sys.stderr)

        elif self._method == self.METHOD_SETXKBMAP:
            print("Cycling layout using setxkbmap...")
            current_index = self.get_current_layout_index()
            if not (0 <= current_index < num_layouts):
                 print(f"WARNING: Current index {current_index} was invalid before cycling. Starting from 0.", file=sys.stderr)
                 current_index = 0
            next_index = (current_index + 1) % num_layouts
            success = self.set_layout_by_index(next_index, update_system=True)
        else:
            print("ERROR: Cannot cycle layout, no valid method.", file=sys.stderr)
            return False

        return success
    # --- *** نهاية التعديل *** ---


    # --- *** دوال المراقبة الجديدة *** ---
    def can_monitor(self) -> bool:
        """Checks if monitoring layout changes using xkb-switch is possible."""
        return self._method == self.METHOD_XKB_SWITCH

    def start_change_monitor(self):
        """Starts monitoring layout changes in a background thread using 'xkb-switch -W'."""
        if not self.can_monitor():
            print("Monitoring not available (requires xkb-switch).")
            return
        if self._monitoring_active:
            print("Monitor thread already active.")
            return

        print("Starting xkb-switch layout monitor thread...")
        self._stop_monitor_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitoring_active = True
        self._monitor_thread.start()

    def stop_change_monitor(self):
        """Stops the layout change monitoring thread."""
        if not self._monitoring_active or not self._monitor_thread:
            return

        print("Stopping xkb-switch layout monitor thread...")
        self._stop_monitor_event.set() # Signal the thread to stop

        # Terminate the process if it's running
        if self._monitor_process:
            try:
                print("Terminating xkb-switch -W process...")
                self._monitor_process.terminate()
                # Wait briefly for termination
                self._monitor_process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                print("Process did not terminate, killing...")
                self._monitor_process.kill()
            except Exception as e:
                print(f"Error terminating monitor process: {e}")
            finally:
                self._monitor_process = None

        # Wait for the thread to finish
        self._monitor_thread.join(timeout=1.0)
        if self._monitor_thread.is_alive():
            print("WARNING: Monitor thread did not exit cleanly.", file=sys.stderr)

        self._monitoring_active = False
        self._monitor_thread = None
        print("Monitor thread stopped.")

    def _monitor_loop(self):
        """The actual monitoring loop running in a thread."""
        print("xkb-switch monitor thread started.")
        while not self._stop_monitor_event.is_set():
            try:
                print("Monitor: Launching xkb-switch -W...")
                # Use Popen to continuously read output without blocking
                self._monitor_process = subprocess.Popen(
                    [self._xkb_switch_path, '-W'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, # Capture errors too
                    text=True,
                    bufsize=1, # Line buffered
                    errors='ignore' # Ignore decoding errors if any
                )

                # Read output line by line
                for line in iter(self._monitor_process.stdout.readline, ''):
                    if self._stop_monitor_event.is_set():
                        print("Monitor: Stop event received, breaking loop.")
                        break
                    new_layout = line.strip()
                    if new_layout:
                        print(f"Monitor: Detected layout change -> {new_layout}")
                        # Update internal state and emit signal
                        if new_layout in self._available_layouts:
                            try:
                                new_index = self._available_layouts.index(new_layout)
                                self._set_internal_index(new_index, emit_signal=True)
                            except ValueError:
                                print(f"Monitor Warning: '{new_layout}' not in known layouts after change.", file=sys.stderr)
                                # Optionally refresh the list if layout isn't known
                                # self.refresh()
                        else:
                             print(f"Monitor Warning: Received unknown layout '{new_layout}'. Refreshing list.", file=sys.stderr)
                             self.refresh() # Refresh list if layout is completely new
                             # Re-check and set index after refresh
                             if new_layout in self._available_layouts:
                                 try:
                                     new_index = self._available_layouts.index(new_layout)
                                     self._set_internal_index(new_index, emit_signal=True)
                                 except ValueError: pass


                # Check process exit status after loop ends
                self._monitor_process.wait() # Wait for process to finish if loop exited normally
                return_code = self._monitor_process.poll()
                print(f"Monitor: xkb-switch -W process exited with code {return_code}.")
                # Read any remaining stderr
                stderr_output = self._monitor_process.stderr.read()
                if stderr_output:
                     print(f"Monitor: xkb-switch -W stderr:\n{stderr_output}", file=sys.stderr)

            except FileNotFoundError:
                print("Monitor ERROR: xkb-switch command disappeared?", file=sys.stderr)
                self._monitoring_active = False # Stop trying if command gone
                break
            except Exception as e:
                print(f"Monitor ERROR: Exception in loop: {e}", file=sys.stderr)
                # Avoid busy-looping on persistent errors
                time.sleep(5)

            finally:
                 # Ensure process is cleaned up if it exists
                 if self._monitor_process and self._monitor_process.poll() is None:
                      try:
                           self._monitor_process.terminate()
                           self._monitor_process.wait(timeout=0.2)
                      except: pass
                      if self._monitor_process.poll() is None:
                           self._monitor_process.kill()
                 self._monitor_process = None

            # If the loop exited (e.g., process died), wait before retrying
            if not self._stop_monitor_event.is_set():
                print("Monitor: Process exited unexpectedly, restarting in 5 seconds...")
                time.sleep(5)

        print("xkb-switch monitor thread finished.")
    # --- *** نهاية دوال المراقبة *** ---

# file:XKB_Switcher.py
