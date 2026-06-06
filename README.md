# pywmdock

`pywmdock` is a lightweight, Python-based dockapp manager for X11 environments. It is designed to capture WindowMaker-style "dockapps" and organize them into a clean, customizable panel. Written in the spirit of the XFCE 4.12-era xfce4-wmdock-plugin.

Includes a GTK-based configuration panel for managing your dock layout, orientation, and app list, supports drag-n-drop, anchoring to corners for individual monitors and different window hints (`dock`, `always-above`, `always-below`) to control how the dock interacts with your workspace.

![screenshot](/screenshot.png)

## Why?

Because dockapps are cool. I doubt many people are still left in the world using them - many of them are over twenty years old - but it's a shame to see them become unusable outside of WindowMaker, and running them in windowed mode is not ideal.

There is an excellent port of xfce4-wmdock-plugin for newer XFCE versions/GTK3 here: https://github.com/maurerpe/xfce4-wmdock-plugin, however I am no longer using XFCE and wanted something desktop or workspace agnostic.

## Prerequisites

* `python3`
* `python3-gi` (PyGObject)
* `python3-gi-cairo`
* `gir1.2-gtk-3.0`
* `gir1.2-wnck-3.0`
* `python3-xlib`

On Debian:

```
sudo apt update
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-wnck-3.0 python3-xlib
```

## Installation & Setup

`pip install -U git+https://github.com/tezeta/pywmdock.git`

## Usage

### Launching the Dock
To start the dock:
```bash
pywmdock
```

### Configuring the Dock
To open settings:
```bash
pywmdock --config
```
