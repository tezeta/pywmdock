"""
pywmdock

defaults.py

tezeta 2026
"""

import os

PROJECT_NAME = "pywmdock"
CONFIG_PATH = os.path.expanduser(f'~/.config/{PROJECT_NAME}')

DEFAULT_SETTINGS = {
    'orientation': 'vertical',
    'anchor': 'top-right',
    'monitor_index': '2',
    'offset_x': '0',
    'offset_y': '0',
    'dockapp_spacing': '0',
    'background_image': '',
    'detection_regex': '^(wm)',
    'stacking_mode': 'always-below'
}