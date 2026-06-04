"""
pywmdock

util.py
Various utilities

tezeta 2026
"""

from importlib import resources

def get_image_path(filename):
    with resources.path('pywmdock.res', filename) as path:
        return str(path)
