# -*- coding: utf-8 -*-
# File: XKB_Switcher.py
# Manages keyboard layouts using the 'setxkbmap' command-line tool.

import subprocess
import re
import os
import sys # For stderr
from typing import List, Optional, Tuple

class XKBManagerError(Exception):
    """ Custom exception for errors within XKBManager. """
    pass

class XKBManager:
    """
    Manages keyboard layouts using the 'setxkbmap' command-line tool on Linux/X11.
    Allows querying available layouts, getting the current layout, setting layouts by index or name,
    and cycling through available layouts.
    """

    def __init__(self, auto_refresh: bool = True):
        """
        Initializes the XKBManager.

        Args:
            auto_refresh (bool): If True, automatically fetches the available
                                 layouts and attempts to determine the initial
                                 system layout upon initialization. Defaults to True.
        """
        self._available_layouts: List[str] = [] # Cache for available layout names (e.g., ['us', 'ara'])
        self._current_layout_index: int = -1 # Internal index representing the believed current layout (-1 = unknown)

        if auto_refresh:
            # Perform initial refresh and detection
            self.refresh()
            # Attempt to determine initial index *after* refreshing the list
            initial_layout_name = self._query_and_parse_first_layout()
            if initial_layout_name and initial_layout_name in self._available_layouts:
                try:
                    # Find the index of the detected layout in our refreshed list
                    self._current_layout_index = self._available_layouts.index(initial_layout_name)
                    print(f"Initial system layout detected: '{initial_layout_name}', index: {self._current_layout_index}")
                except ValueError:
                    print(f"WARNING: Initial system layout '{initial_layout_name}' found but not in internal list after refresh.", file=sys.stderr)
                    self._current_layout_index = 0 if self._available_layouts else -1 # Fallback
            else:
                # Couldn't detect or detected layout not in our list
                if initial_layout_name:
                     print(f"WARNING: Initial system layout '{initial_layout_name}' not in available layouts: {self._available_layouts}", file=sys.stderr)
                else:
                     print("Could not reliably determine initial layout index, defaulting.")
                # Default to the first layout (index 0) if any are available
                self._current_layout_index = 0 if self._available_layouts else -1

    def _run_command(self, command_list: List[str], timeout: float = 0.5) -> Optional[str]:
        """ Runs an external command and returns its stdout, or None on failure. """
        try:
            # Ensure environment variables (like DISPLAY) are passed
            env = os.environ.copy()
            # Execute the command
            result = subprocess.run(
                command_list,
                capture_output=True, # Capture stdout and stderr
                text=True,           # Decode output as text
                check=True,          # Raise CalledProcessError on non-zero exit code
                timeout=timeout,     # Set a timeout to prevent hangs
                env=env              # Pass environment
            )
            return result.stdout.strip() # Return stripped stdout on success
        except FileNotFoundError:
            # Handle case where setxkbmap command is not found
            raise XKBManagerError(f"Command not found: '{command_list[0]}'. Is setxkbmap installed and in PATH?")
        except subprocess.CalledProcessError as e:
            # Handle errors reported by the command itself (non-zero exit code)
            # print(f"WARNING: Command '{' '.join(command_list)}' failed with code {e.returncode}. Stderr: {e.stderr.strip()}", file=sys.stderr) # Less verbose
            return None # Indicate failure
        except subprocess.TimeoutExpired:
            # Handle command timeout
            print(f"WARNING: Command '{' '.join(command_list)}' timed out after {timeout} seconds.", file=sys.stderr)
            return None # Indicate failure
        except Exception as e:
            # Catch any other unexpected errors during command execution
            print(f"WARNING: Unexpected error running {' '.join(command_list)}: {e}", file=sys.stderr)
            return None # Indicate failure

    def _query_and_parse_first_layout(self) -> Optional[str]:
        """ Runs 'setxkbmap -query' and parses the *first* layout name found. """
        # Execute the query command
        output = self._run_command(['setxkbmap', '-query'])
        if output:
            # Use regex to find the 'layout:' line and capture the layout names
            layout_match = re.search(r'layout:\s*([\w,]+)', output)
            if layout_match:
                # Split the comma-separated list and return the first one
                layouts = layout_match.group(1).split(',')
                if layouts:
                    return layouts[0] # Return the first layout (assumed to be active)
            else:
                # Handle case where 'layout:' line is missing or malformed
                print("WARNING: Could not parse 'layout:' line from setxkbmap query.", file=sys.stderr)
        return None # Return None if command failed or parsing failed

    def refresh(self) -> bool:
        """
        Refreshes the internal list of *available* layouts by running 'setxkbmap -query'.
        Updates self._available_layouts.

        Returns:
            bool: True if the layout list was successfully obtained and parsed, False otherwise.
        """
        output = self._run_command(['setxkbmap', '-query'])
        if output is None:
             print("ERROR: Failed to execute 'setxkbmap -query' during refresh.", file=sys.stderr)
             return False # Indicate failure

        # Parse the layout line from the output
        new_layouts = []
        layout_match = re.search(r'layout:\s*([\w,]+)', output)
        if layout_match:
            new_layouts = layout_match.group(1).split(',')
        else:
            print("WARNING: Could not parse 'layout:' line from setxkbmap query during refresh.", file=sys.stderr)
            return False # Indicate failure to parse

        # Check if the set of available layouts has actually changed
        if set(new_layouts) != set(self._available_layouts):
            print(f"Available layout set updated: {self._available_layouts} -> {new_layouts}")
            self._available_layouts = new_layouts # Update the internal list
            # --- Re-validate the current index after list change ---
            if not (0 <= self._current_layout_index < len(self._available_layouts)):
                print(f"Current layout index {self._current_layout_index} became invalid after list update, resetting.")
                # Attempt to re-detect current layout from system AFTER list update
                current_name_now = self._query_and_parse_first_layout()
                if current_name_now and current_name_now in self._available_layouts:
                    try:
                        self._current_layout_index = self._available_layouts.index(current_name_now)
                        print(f"  -> Re-detected current layout '{current_name_now}' at new index {self._current_layout_index}")
                    except ValueError:
                        self._current_layout_index = 0 # Fallback to first layout
                else:
                     self._current_layout_index = 0 if self._available_layouts else -1 # Fallback

        # --- Final Index Sanity Check ---
        if not self._available_layouts:
            self._current_layout_index = -1
        elif not (0 <= self._current_layout_index < len(self._available_layouts)):
             print(f"WARNING: Current layout index {self._current_layout_index} invalid after refresh, resetting to 0.", file=sys.stderr)
             self._current_layout_index = 0

        return True # Indicate refresh attempt was successful (list obtained)

    def query_current_layout_name(self) -> Optional[str]:
        """
        Queries the system using 'setxkbmap -query' and returns the *currently active*
        layout name (assumed to be the first one listed).

        Returns:
            Optional[str]: The name of the currently active layout, or None if query fails.
        """
        return self._query_and_parse_first_layout()

    def get_available_layouts(self) -> List[str]:
        """
        Returns the cached list of available layout names (e.g., ['us', 'ara']).
        """
        return self._available_layouts

    def get_current_layout_index(self) -> int:
        """
        Returns the index the manager *believes* is currently active based on its internal state.
        Returns -1 if no layouts are available or state is unknown.
        """
        if not self._available_layouts:
            return -1
        if not (0 <= self._current_layout_index < len(self._available_layouts)):
             return 0 # Return index 0 as a safe default if list exists but index is bad
        return self._current_layout_index

    def get_current_layout_name(self) -> Optional[str]:
        """
        Returns the name of the layout the manager *believes* is currently active.
        Returns None if no layouts are available or state is unknown.
        """
        index = self.get_current_layout_index()
        if 0 <= index < len(self._available_layouts):
            return self._available_layouts[index]
        return None

    def _set_internal_index(self, index: int):
        """ Safely sets the internal current layout index. """
        if 0 <= index < len(self._available_layouts):
            if self._current_layout_index != index:
                 self._current_layout_index = index
        elif len(self._available_layouts) > 0:
            print(f"WARNING: Attempted to set invalid internal index {index}. Setting to 0.", file=sys.stderr)
            self._current_layout_index = 0
        else:
             self._current_layout_index = -1


    def set_layout_by_index(self, index: int, update_system: bool = True) -> bool:
        """
        Attempts to set the active layout to the one at the specified index.

        Args:
            index (int): The 0-based index of the desired layout.
            update_system (bool): If True, executes 'setxkbmap'. If False, only updates internal state.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        if not (0 <= index < len(self._available_layouts)):
            print(f"ERROR: Invalid layout index {index} requested. Available: {len(self._available_layouts)} layouts.", file=sys.stderr)
            return False

        target_layout = self._available_layouts[index]

        if update_system:
            print(f"Attempting to set system layout to index {index} ('{target_layout}')...")
            reordered_layouts = [target_layout] + [l for i, l in enumerate(self._available_layouts) if i != index]
            layout_string = ",".join(reordered_layouts)
            command = ['setxkbmap', '-layout', layout_string]

            if self._run_command(command) is not None:
                print(f"System layout change command likely succeeded.")
                self._set_internal_index(index)
                return True
            else:
                print(f"ERROR: System layout change command failed for '{target_layout}'.", file=sys.stderr)
                return False
        else:
            self._set_internal_index(index)
            return True


    def set_layout_by_name(self, name: str, update_system: bool = True) -> bool:
        """
        Attempts to set the active layout to the one matching the given name.

        Args:
            name (str): The name of the desired layout (e.g., 'ara', 'us').
            update_system (bool): If True, executes 'setxkbmap'. If False, only updates internal index.

        Returns:
            bool: True if the layout name was found and the operation was successful, False otherwise.
        """
        try:
            index = self._available_layouts.index(name)
            return self.set_layout_by_index(index, update_system=update_system)
        except ValueError:
            print(f"ERROR: Layout name '{name}' not found in available layouts: {self._available_layouts}", file=sys.stderr)
            return False
        except Exception as e:
             print(f"ERROR finding index for layout name '{name}': {e}", file=sys.stderr)
             return False

    def cycle_next_layout(self) -> bool:
        """
        Attempts to switch the *system* layout to the next one in the internal list.

        Returns:
            bool: True if switching was attempted successfully, False otherwise.
        """
        num_layouts = len(self._available_layouts)
        if num_layouts <= 1:
            print("Not enough layouts configured in the system to cycle.")
            return False

        current_index = self.get_current_layout_index()
        if not (0 <= current_index < num_layouts):
             print(f"WARNING: Current index {current_index} was invalid before cycling. Starting from 0.", file=sys.stderr)
             current_index = 0

        next_index = (current_index + 1) % num_layouts
        print(f"Cycling layout: Index {current_index} -> {next_index}")

        return self.set_layout_by_index(next_index, update_system=True)
