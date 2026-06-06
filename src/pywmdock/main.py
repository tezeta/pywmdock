#!/usr/bin/env python3
"""
pywmdock

A Python dock for WindowMaker dockapps, in the spirit of xfce4-wmdock-plugin

tezeta 2026
"""

import os
import logging
import signal
import fcntl
import sys
import argparse
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .wmdock import WMDockPanel
from .ui import ConfigWindow
from .defaults import CONFIG_PATH

def main():
    parser = argparse.ArgumentParser(description="PyWMDock")
    parser.add_argument('--config', action='store_true', help="Launch configuration panel")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging")
    args = parser.parse_args()

    # Configure Logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    if args.config:
        win = ConfigWindow()
        Gtk.main()
    else:
        signal.signal(signal.SIGUSR1, reload_app_config)

        # Single instance lock
        lock_file = os.path.join(CONFIG_PATH, 'pywmdock.lock')
        fp = open(lock_file, 'w')
        try:
            fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fp.write(str(os.getpid()))
            fp.flush()
        except IOError:
            print("Another instance is already running.")
            sys.exit(1)

        logging.info("Launching PyWMDock...")
        panel = WMDockPanel()
        Gtk.main()

def reload_app_config(signum, frame):
    logging.info("Received SIGUSR1 signal. Reloading configuration...")
    os.execl(sys.executable, sys.executable, *sys.argv)

if __name__ == '__main__':
    main()