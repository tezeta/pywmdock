"""
pywmdock

config_ui.py
contains GUI class for modifying settings

tezeta 2026
"""

import os
import signal
import json
import configparser
from importlib import resources
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk

from .defaults import PROJECT_NAME, CONFIG_PATH
from .util import get_image_path

class ConfigWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="PyWMDock Settings")
        self.set_default_size(500, 650)
        self.set_border_width(15)

        self.set_icon_from_file(get_image_path("GNUstep_logo.svg")) 

        self.config_path = os.path.join(CONFIG_PATH, 'config.ini')
        self.state_file = os.path.join(CONFIG_PATH, 'state.json')

        self.settings_widgets = {}

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.add(main_box)

        # Settings Grid
        grid = Gtk.Grid(column_spacing=20, row_spacing=10)
        main_box.pack_start(grid, False, False, 0)

        row = 0
        self.add_dropdown(grid, row, "Orientation: ", "orientation", ["vertical", "horizontal"])
        row += 1
        self.add_dropdown(grid, row, "Stacking Mode: ", "stacking_mode",
                        ["dock", "always-above", "always-below"])        
        row += 1
        self.add_dropdown(grid, row, "Anchor: ", "anchor", ["top-left", "top-right", "bottom-left", "bottom-right"])
        row += 1
        self.add_monitor_dropdown(grid, row)
        row += 1
        self.add_spin_button(grid, row, "Offset X: ", "offset_x")
        row += 1
        self.add_spin_button(grid, row, "Offset Y: ", "offset_y")
        row += 1
        self.add_entry(grid, row, "Background Image (leave blank for default): ", "background_image")
        row += 1
        self.add_entry(grid, row, "Detection Regex: ", "detection_regex")

        # Apps List
        main_box.pack_start(Gtk.Label(label="<b>Saved Apps</b>", use_markup=True), False, False, 5)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(250)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_box.pack_start(scrolled, True, True, 0)

        self.listbox = Gtk.ListBox()
        scrolled.add(self.listbox)

        self.reload_data()

        # Button Box
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_end(btn_box, False, False, 5)

        reload_btn = Gtk.Button(label="Reload")
        reload_btn.connect("clicked", self.reload_data)
        btn_box.pack_start(reload_btn, True, True, 0)

        save_btn = Gtk.Button(label="Save All Changes")
        save_btn.connect("clicked", self.save_all)
        btn_box.pack_start(save_btn, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.show_all()

    def add_entry(self, grid, row, label_text, config_key):
        grid.attach(Gtk.Label(label=label_text, xalign=0), 0, row, 1, 1)
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        grid.attach(entry, 1, row, 1, 1)
        self.settings_widgets[config_key] = entry

    def add_dropdown(self, grid, row, label_text, config_key, options):
        grid.attach(Gtk.Label(label=label_text, xalign=0), 0, row, 1, 1)
        combo = Gtk.ComboBoxText()
        combo.set_hexpand(True)
        for opt in options:
            combo.append(opt, opt)
        grid.attach(combo, 1, row, 1, 1)
        self.settings_widgets[config_key] = combo

    def add_monitor_dropdown(self, grid, row):
        grid.attach(Gtk.Label(label="Monitor Index", xalign=0), 0, row, 1, 1)
        combo = Gtk.ComboBoxText()
        combo.set_hexpand(True)
        display = Gdk.Display.get_default()
        for i in range(display.get_n_monitors()):
            combo.append(str(i), f"Monitor {i}")
        grid.attach(combo, 1, row, 1, 1)
        self.settings_widgets['monitor_index'] = combo

    def add_spin_button(self, grid, row, label_text, config_key):
        grid.attach(Gtk.Label(label=label_text, xalign=0), 0, row, 1, 1)
        adj = Gtk.Adjustment(value=0, lower=-500, upper=2000, step_increment=1)
        spin = Gtk.SpinButton(adjustment=adj)
        spin.set_hexpand(True)
        grid.attach(spin, 1, row, 1, 1)
        self.settings_widgets[config_key] = spin

    def reload_data(self, *args):
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)

        for key, widget in self.settings_widgets.items():
            val = self.config.get(PROJECT_NAME, key, fallback='')
            if isinstance(widget, Gtk.ComboBoxText):
                widget.set_active_id(val)
            elif isinstance(widget, Gtk.SpinButton):
                widget.set_value(float(val) if val else 0)
            elif isinstance(widget, Gtk.Entry):
                widget.set_text(val)

        self.load_app_list()

    def load_app_list(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                apps = json.load(f)
                for app in apps:
                    row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                    name_lbl = Gtk.Label(label=app['name'], xalign=0)
                    name_lbl.set_size_request(100, -1)
                    row_box.pack_start(name_lbl, False, False, 5)

                    cmd_entry = Gtk.Entry()
                    cmd_entry.set_text(" ".join(app['command']) if isinstance(app['command'], list) else app['command'])
                    row_box.pack_start(cmd_entry, True, True, 5)

                    up_btn = Gtk.Button(label="↑")
                    up_btn.connect("clicked", self.move_row, -1)
                    row_box.pack_start(up_btn, False, False, 2)

                    down_btn = Gtk.Button(label="↓")
                    down_btn.connect("clicked", self.move_row, 1)
                    row_box.pack_start(down_btn, False, False, 2)

                    del_btn = Gtk.Button(label="X")
                    del_btn.connect("clicked", self.remove_app_row)
                    row_box.pack_end(del_btn, False, False, 5)
                    self.listbox.add(row_box)
        self.listbox.show_all()

    def move_row(self, button, direction):
        row = button.get_parent().get_parent()
        index = row.get_index()
        new_index = index + direction
        if 0 <= new_index < len(self.listbox.get_children()):
            self.listbox.remove(row)
            self.listbox.insert(row, new_index)
            button.grab_focus()

    def remove_app_row(self, button):
        self.listbox.remove(button.get_parent().get_parent())

    def save_all(self, widget):
        config = configparser.ConfigParser()
        config.add_section(PROJECT_NAME)
        for key, widget in self.settings_widgets.items():
            if isinstance(widget, Gtk.ComboBoxText):
                config.set(PROJECT_NAME, key, widget.get_active_id())
            elif isinstance(widget, Gtk.SpinButton):
                config.set(PROJECT_NAME, key, str(widget.get_value_as_int()))
            elif isinstance(widget, Gtk.Entry):
                config.set(PROJECT_NAME, key, widget.get_text())

        with open(self.config_path, 'w') as f:
            config.write(f)

        new_state = []
        for row in self.listbox.get_children():
            children = row.get_child().get_children()
            name = children[0].get_text()
            cmd = children[1].get_text()
            new_state.append({"name": name, "command": cmd.split()})
        with open(self.state_file, 'w') as f:
            json.dump(new_state, f, indent=4)

        lock_file = os.path.join(CONFIG_PATH, 'pywmdock.lock')
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    pid = int(f.read().strip())

                # Send the signal
                os.kill(pid, signal.SIGUSR1)
                print(f"Sent reload signal to process {pid}")
            except (ProcessLookupError, ValueError):
                # The process in the lock file doesn't exist
                print("Lock file found but process is dead. Continuing.")
            except Exception as e:
                print(f"Failed to signal app: {e}")
        #self.destroy()