"""
pywmdock

wmdock.py
Provides a dock to insert dockapps into.

tezeta 2026
"""

import os
import logging
import signal
import re
import json
import configparser
import subprocess
import time
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import Gtk, Wnck, GLib, Gdk, GdkPixbuf

from .dockapp import DockAppWidget
from .defaults import PROJECT_NAME, CONFIG_PATH, DEFAULT_SETTINGS
from .util import get_image_path

os.makedirs(CONFIG_PATH, exist_ok=True)

class WMDockPanel(Gtk.Window):
    """
    WMDockPanel - a container for dockapps
    """

    def __init__(self):
        super().__init__()
        self.dockapps = []
        self.widgets_map = {}
        self.app_commands = {}

        self.load_config()
        self.setup_ui()

        self.screen = Wnck.Screen.get_default()
        GLib.idle_add(self.initial_scan)

        # handle open/closed windows
        self.screen.connect("window-opened", self.on_window_opened)
        self.screen.connect("window-closed", self.on_window_closed)

    @property
    def is_append_mode(self):
        """True when new apps should be appended to the end of the list.
        Bottom/right anchors grow toward the top/left, so appending keeps visual order correct."""
        return "bottom" in self.anchor or "right" in self.anchor

    def get_window_command(self, window):
        """Reads the Linux process tree to find the exact launch command of the app."""
        pid = window.get_pid()
        if pid <= 0:
            return None
        try:
            with open(f"/proc/{pid}/cmdline", "r") as f:
                cmd_parts = f.read().split('\x00')
                cmd_parts = [p for p in cmd_parts if p]
                if cmd_parts:
                    return cmd_parts
        except Exception:
            pass
        return None

    @property
    def is_reverse_mode(self):
        """Returns True if we should mirror/reverse the dock layout."""
        if self.orientation == 'horizontal' and 'right' in self.anchor:
            return True
        if self.orientation == 'vertical' and 'bottom' in self.anchor:
            return True
        return False

    def save_state(self):
        """Dumps the current layout and commands to state.json."""
        state_file = os.path.join(CONFIG_PATH, 'state.json')
        state_data = []
        for win in self.dockapps:
            cmd = self.app_commands.get(win.get_xid())
            if cmd:
                state_data.append({
                    "name": win.get_name(),
                    "command": cmd
                })

        try:
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=4)
        except Exception as e:
            logging.warning(f"Failed to save state: {e}")

    def load_and_restore_state(self):
        """Revives dockapps that were running before the script was closed."""
        state_file = os.path.join(CONFIG_PATH, 'state.json')
        if not os.path.exists(state_file):
            return

        try:
            with open(state_file, 'r') as f:
                saved_apps = json.load(f)

            # Get the commands currently running so we don't spawn duplicates
            # We map XIDs to their command strings
            running_cmds = [
                str(self.app_commands[w.get_xid()])
                for w in self.dockapps
                if self.app_commands.get(w.get_xid())
            ]

            # We simply iterate through the saved list linearly.
            # If we are in 'reverse mode' (pack_end), the linear order
            # will be automatically reversed visually, which is exactly what we want.
            spawn_delay = 0
            for app in saved_apps:
                cmd = app.get("command")
                if not cmd:
                    continue

                if str(cmd) not in running_cmds:
                    logging.debug(f"Restoring from state: {cmd}")
                    # Use a slight delay to ensure they are added in the specific order
                    GLib.timeout_add(spawn_delay, self.spawn_app, cmd)
                    spawn_delay += 250 # Reduced delay for faster startup

        except Exception as e:
            logging.warning(f"Could not load state: {e}")

    def spawn_app(self, cmd):
        """Helper function used to spawn dockapps."""
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logging.warning(f"Failed to spawn {cmd}: {e}")
        return False

    def initial_scan(self):
        # Clean up old/hidden instances first
        self.clean_stale_processes()

        # Wait a moment for processes to exit
        import time
        time.sleep(0.5)

        # Proceed with existing scan logic
        self.screen.force_update()
        for window in self.screen.get_windows():
            self.check_and_add(window, update_state=False)

        self.load_and_restore_state()
        return False

    def load_config(self):
        config = configparser.ConfigParser()
        config_file = os.path.join(CONFIG_PATH, 'config.ini')

        # Check if file exists, if not, create it
        if not os.path.exists(config_file):
            self.write_defaults()

        # Read the file
        config.read(config_file)

        # Ensure the section exists in the config object so fallbacks work
        if not config.has_section(PROJECT_NAME):
            config.add_section(PROJECT_NAME)

        # Helper to get values with defaults from our dictionary
        def get_setting(key, cast_func=str):
            val = config.get(PROJECT_NAME, key, fallback=DEFAULT_SETTINGS.get(key))
            return cast_func(val)

        # Apply settings
        self.orientation = get_setting('orientation')
        self.stacking_mode = get_setting('stacking_mode')
        self.anchor = get_setting('anchor')
        self.monitor_index = get_setting('monitor_index', int)
        self.offset_x = get_setting('offset_x', int)
        self.offset_y = get_setting('offset_y', int)
        self.background_image = get_setting('background_image') or get_image_path("tile.png") # fallback to tile image if not set
        self.detection_regex = get_setting('detection_regex')

        # Load background image logic
        self.bg_pixbuf = None
        if self.background_image and os.path.exists(self.background_image):
            try:
                logging.debug(f"Using background image: {self.background_image}")
                self.bg_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(self.background_image, 64, 64, False)
            except Exception as e:
                logging.warning(f"Failed to load background image: {e}")

    def setup_ui(self):
        self.set_title("PyWMDock Panel")
        self.set_wmclass("pywmdock", "PyWMDock")
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_decorated(False)
        self.set_resizable(False)
        self.stick()
        self.set_default_size(1, 1)

        self.apply_stacking_mode()

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and self.is_composited():
            self.set_visual(visual)
            self.set_app_paintable(True)
            self.connect("draw", self.on_draw_transparent)

        is_vert = (self.orientation == 'vertical')
        self.box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL if is_vert else Gtk.Orientation.HORIZONTAL,
            spacing=0
        )
        self.add(self.box)

        # "size-allocate" fires whenever child widgets change the panel's size,
        # so it catches both the initial layout and any later additions/removals.
        # "realize" fires too early — the window size is still (1,1) at that point.
        self.connect("size-allocate", self.on_size_allocate)

        # We also listen to size allocation to dynamically recalculate struts
        # whenever dockapps are added or removed!
        self.connect("size-allocate", self.update_dock_struts)

    def apply_stacking_mode(self):
        # Reset existing states
        self.set_keep_above(False)
        self.set_keep_below(False)

        mode = getattr(self, 'stacking_mode', 'dock')
        if mode == 'dock':
            # DOCK type hint tells the WM that this is a system panel
            self.set_type_hint(Gdk.WindowTypeHint.DOCK)
            # Docks usually want to sit above wallpapers but behind fullscreen apps
            self.set_keep_above(True)

        elif mode == 'always-above':
            self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
            self.set_keep_above(True)

        elif mode == 'always-below':
            self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
            self.set_keep_below(True)

    def update_dock_struts(self, widget, allocation):
        """Calculates and applies X11 EWMH Struts based on window size, orientation, and anchors."""
        if getattr(self, 'stacking_mode', 'dock') != 'dock':
            return

        # Ensure the window is realized (has an underlying X11 window)
        gdk_window = self.get_window()
        if not gdk_window:
            return

        xid = gdk_window.get_xid()
        if not xid:
            return

        # Import Xlib locally to avoid breaking non-X11 fallbacks
        from Xlib import X, display

        try:
            d = display.Display()
            x_window = d.create_resource_object('window', xid)

            # Fetch the total size of the desktop to properly set geometry limits
            root = d.screen().root
            geom = root.get_geometry()
            screen_width = geom.width
            screen_height = geom.height

            # Get current position and size of the dock panel
            origin = gdk_window.get_origin()
            win_x = origin.x
            win_y = origin.y
            win_w = allocation.width
            win_h = allocation.height

            # Initialize all struts to 0
            left = right = top = bottom = 0
            left_start_y = left_end_y = right_start_y = right_end_y = 0
            top_start_x = top_end_x = bottom_start_x = bottom_end_x = 0

            anchor = self.anchor.lower()

            # Horizontal Layouts (Reserve Y-axis space, span full X-axis width)
            if self.orientation == 'horizontal':
                if "top" in anchor:
                    top = win_y + win_h
                    top_start_x = 0
                    top_end_x = screen_width
                elif "bottom" in anchor:
                    bottom = screen_height - win_y
                    bottom_start_x = 0
                    bottom_end_x = screen_width

            # Vertical Layouts (Reserve X-axis space, span full Y-axis height)
            if self.orientation == 'vertical':
                if "left" in anchor:
                    left = win_x + win_w
                    left_start_y = 0
                    left_end_y = screen_height
                elif "right" in anchor:
                    right = screen_width - win_x
                    right_start_y = 0
                    right_end_y = screen_height

            # Build EWMH Strut Arrays
            strut_partial_values = [
                left, right, top, bottom,
                left_start_y, left_end_y,
                right_start_y, right_end_y,
                top_start_x, top_end_x,
                bottom_start_x, bottom_end_x
            ]
            strut_values = [left, right, top, bottom]

            # Convert string tokens into X11 Atoms
            strut_partial_atom = d.intern_atom('_NET_WM_STRUT_PARTIAL')
            strut_atom = d.intern_atom('_NET_WM_STRUT')
            cardinal_atom = d.intern_atom('CARDINAL')

            # Overwrite the properties on the running X11 window surface
            x_window.change_property(
                strut_partial_atom, cardinal_atom, 32, list(strut_partial_values), X.PropModeReplace
            )
            x_window.change_property(
                strut_atom, cardinal_atom, 32, list(strut_values), X.PropModeReplace
            )

            d.flush()
        except Exception as e:
            logging.warning(f"Failed to set dock window struts: {e}")

    def on_size_allocate(self, widget, allocation):
        # Defer until after GTK finishes the current layout pass so get_size()
        # returns real dimensions rather than stale ones
        GLib.idle_add(self.position_window)

    def on_draw_transparent(self, widget, cr):
        cr.set_source_rgba(0, 0, 0, 0)
        cr.set_operator(1)  # CAIRO_OPERATOR_SOURCE
        cr.paint()
        return False

    def position_window(self, *args):
        display = Gdk.Display.get_default()

        # Check if a specific monitor is requested
        if self.monitor_index >= 0:
            # Safety check: ensure the requested index exists
            if self.monitor_index < display.get_n_monitors():
                monitor = display.get_monitor(self.monitor_index)
            else:
                logging.warning(f"Monitor index {self.monitor_index} not found. Defaulting to primary.")
                monitor = display.get_primary_monitor()
        else:
            monitor = display.get_primary_monitor()

        # get_workarea() accounts for the monitor's x,y position in the virtual desktop
        area = monitor.get_workarea()

        win_w, win_h = self.get_size()

        # The area.x and area.y offset ensures we calculate coordinates
        # relative to that specific monitor's origin, not the global (0,0) screen.
        if "right" in self.anchor:
            x = (area.x + area.width) - win_w - self.offset_x
        else:
            x = area.x + self.offset_x

        if "bottom" in self.anchor:
            y = (area.y + area.height) - win_h - self.offset_y
        else:
            y = area.y + self.offset_y

        self.move(x, y)

    def is_dockapp(self, window):
        """Helper function used to check if a window is a dockapp."""
        # extract standard Window properties
        name = window.get_name() or ""
        class_name = window.get_class_group_name() or ""
        _, _, w, h = window.get_geometry()

        # logging.debug(f"Is '{name}' a dockapp?")

        # ignore ourselves
        class_name = window.get_class_group_name() or ""
        if class_name.lower() == PROJECT_NAME:
            return False

        # filter out types that definitively cannot be dockapps
        if window.get_window_type() not in [
            Wnck.WindowType.NORMAL,
            Wnck.WindowType.DOCK,
            Wnck.WindowType.UTILITY
        ]:
            return False

        # Check standard X11 WM_CLASS flag OR the classic size footprint
        if class_name == "DockApp":
            logging.debug(f"detected DockApp class")
            return True

        if w == 64 and h == 64:
            logging.debug(f"detected DockApp size footprint")
            return True

        # regex fallback
        try:
            if re.search(self.detection_regex, name, re.IGNORECASE) or \
               re.search(self.detection_regex, class_name, re.IGNORECASE):
                # make sure it fits too
                if w <= 64 and h <= 64:
                    logging.debug(f"detected DockApp using regex pattern")
                    return True
        except re.error:
            logging.error(f"Invalid regex pattern: {self.detection_regex}")

        return False

    def check_and_add(self, window, update_state=True):
        if self.is_dockapp(window) and window not in self.dockapps:
            logging.debug(f"Capturing: {window.get_name()}")
            xid = window.get_xid()
            cmd = self.get_window_command(window)
            if cmd:
                self.app_commands[xid] = cmd

            app_widget = DockAppWidget(window, self.bg_pixbuf, self)
            self.widgets_map[xid] = app_widget

            # Use pack_end for reverse mode, pack_start for normal
            if self.is_reverse_mode:
                self.box.pack_end(app_widget, False, False, 0)
            else:
                self.box.pack_start(app_widget, False, False, 0)

            self.dockapps.append(window)
            self.show_all()

            if update_state:
                self.save_state()

    def _check_and_add_window(self, window):
        """Named helper for on_window_opened timeout — avoids lambda trickery."""
        self.check_and_add(window)
        return False

    def on_window_opened(self, screen, window):
        GLib.timeout_add(200, self._check_and_add_window, window)

    def on_window_closed(self, screen, window):
        pass
        # this code causes instant closes...
        # """Fallback for dockapps that close without cleanly removing the plug (e.g. crashes)."""
        # xid = window.get_xid()
        # if any(w.get_xid() == xid for w in self.dockapps):
        #     logging.debug(f"Window closed externally: {xid}")
        #     self.remove_app(xid)

    def write_defaults(self):
        """Creates the initial config.ini file if it doesn't exist."""
        config = configparser.ConfigParser()
        config.add_section(PROJECT_NAME)
        for key, value in DEFAULT_SETTINGS.items():
            # Ensure values are strings for configparser
            config.set(PROJECT_NAME, key, str(value))

        config_file = os.path.join(CONFIG_PATH, 'config.ini')
        with open(config_file, 'w') as f:
            config.write(f)
        logging.info(f"Default configuration written to {config_file}")

    def remove_app(self, xid):
        win_to_remove = next((w for w in self.dockapps if w.get_xid() == xid), None)

        # next() already returns None if not found, so no redundant membership check needed
        if win_to_remove:
            logging.debug(f"Removing from layout: {xid}")
            self.dockapps.remove(win_to_remove)
            self.app_commands.pop(xid, None)

        if xid in self.widgets_map:
            widget_to_remove = self.widgets_map.pop(xid)
            widget_to_remove.destroy()

        self.save_state()

        if not self.dockapps:
            self.hide()

    def reorder_apps(self, source_xid, target_xid):
        src_win = next((w for w in self.dockapps if w.get_xid() == source_xid), None)
        tgt_win = next((w for w in self.dockapps if w.get_xid() == target_xid), None)

        if src_win and tgt_win:
            # 1. Update internal list
            idx_src = self.dockapps.index(src_win)
            idx_tgt = self.dockapps.index(tgt_win)
            self.dockapps.insert(idx_tgt, self.dockapps.pop(idx_src))

            # 2. Update visual order
            # Note: pack_end/start only sets initial placement.
            # reorder_child works regardless of the insertion method!
            self.box.reorder_child(self.widgets_map[source_xid], idx_tgt)

            # Force redraw
            src_widget = self.widgets_map[source_xid]
            src_widget.queue_draw()
            if src_widget.socket.get_realized():
                gdk_win = src_widget.socket.get_window()
                if gdk_win:
                    gdk_win.invalidate_rect(None, True)

            GLib.idle_add(self.position_window)
            self.save_state()

    def clean_stale_processes(self):
        """Finds and terminates processes that match the known dockapp commands."""
        state_file = os.path.join(CONFIG_PATH, 'state.json')
        if not os.path.exists(state_file):
            return

        try:
            with open(state_file, 'r') as f:
                apps = json.load(f)

            for app in apps:
                cmd_list = app.get("command", [])
                if not cmd_list:
                    continue

                # Turn the command list back into a string for matching
                cmd_str = " ".join(cmd_list)

                # Use pgrep to find PID(s) of this process
                # -f matches the full command line
                result = subprocess.run(['pgrep', '-f', cmd_str], capture_output=True, text=True)

                if result.stdout:
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid == str(os.getpid()): continue # Don't kill ourself!

                        logging.debug(f"Cleaning up stale process {pid} for command: {cmd_str}")
                        try:
                            os.kill(int(pid), signal.SIGKILL) # SIGTERM
                        except ProcessLookupError:
                            pass

        except Exception as e:
            logging.warning(f"Error during process cleanup: {e}")