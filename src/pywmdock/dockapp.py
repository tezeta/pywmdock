"""
pywmdock

dockapp.py
Provides a container for dockapps.

tezeta 2026
"""

import gi
import logging
gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import Gtk, Wnck, GLib, Gdk, GdkPixbuf

class DockAppWidget(Gtk.EventBox):
    """
    DockAppWidget - handles individual dockapps
    """

    def __init__(self, window, bg_pixbuf, parent_panel):
        super().__init__()
        self.window = window
        self.xid = window.get_xid()
        self.parent_panel = parent_panel
        self.bg_pixbuf = bg_pixbuf

        self.set_size_request(64, 64)
        self.set_app_paintable(True)
        self.connect("draw", self.on_draw)

        # Use a Fixed container so we can manually center the socket
        self.fixed = Gtk.Fixed()
        self.fixed.set_size_request(64, 64)
        self.add(self.fixed)

        self.socket = Gtk.Socket()
        self.fixed.put(self.socket, 0, 0)  # Placeholder; centered after realize

        self.socket.connect("realize", self.on_socket_realized)
        self.socket.connect("plug-removed", self.on_plug_removed)

        self.setup_dnd()
        self.show_all()

    def on_socket_realized(self, widget):
        try:
            # Draw background onto the socket's own GDK window before embedding
            gdk_win = widget.get_window()
            if gdk_win and self.bg_pixbuf:
                cr = gdk_win.cairo_create()
                cr.set_operator(1)  # CAIRO_OPERATOR_SOURCE
                Gdk.cairo_set_source_pixbuf(cr, self.bg_pixbuf, 0, 0)
                cr.paint()
                del cr

            widget.add_id(self.xid)

            # Defer centering — the plug needs a moment to negotiate its size
            GLib.idle_add(self.center_socket)

        except Exception as e:
            logging.warning(f"Failed to embed window {self.xid}: {e}")

    def on_plug_removed(self, widget):
        logging.debug(f"Dockapp natively closed: {self.xid}")
        self.parent_panel.remove_app(self.xid)
        return False

    def center_socket(self):
        _, _, app_w, app_h = self.window.get_geometry()

        # Clamp to our 64x64 box in case something reports larger
        app_w = min(app_w, 64)
        app_h = min(app_h, 64)

        offset_x = (64 - app_w) // 2
        offset_y = (64 - app_h) // 2

        self.socket.set_size_request(app_w, app_h)
        self.fixed.move(self.socket, offset_x, offset_y)

        self.queue_draw()
        return False  # Don't repeat

    def on_draw(self, widget, cr):
        # Clear to transparent first
        cr.set_operator(1)  # CAIRO_OPERATOR_SOURCE
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()

        # Paint background on the EventBox layer
        if self.bg_pixbuf:
            Gdk.cairo_set_source_pixbuf(cr, self.bg_pixbuf, 0, 0)
            cr.paint()

        # Also repaint the socket's own GDK window — it's a native X11 window
        # and won't inherit the EventBox draw, so we push pixels into it directly
        if self.bg_pixbuf and self.socket.get_realized():
            gdk_win = self.socket.get_window()
            if gdk_win:
                sock_cr = gdk_win.cairo_create()
                sock_cr.set_operator(1)  # CAIRO_OPERATOR_SOURCE
                Gdk.cairo_set_source_pixbuf(sock_cr, self.bg_pixbuf, 0, 0)
                sock_cr.paint()
                del sock_cr

        return False

    def setup_dnd(self):
        entries = [Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_APP, 0)]
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, entries, Gdk.DragAction.MOVE)
        self.drag_dest_set(Gtk.DestDefaults.ALL, entries, Gdk.DragAction.MOVE)

        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)

    def on_drag_data_get(self, widget, context, data, info, time):
        data.set_text(str(self.xid), -1)

    def on_drag_data_received(self, widget, context, x, y, data, info, time):
        source_xid = int(data.get_text())
        self.parent_panel.reorder_apps(source_xid, self.xid)
        Gtk.drag_finish(context, True, False, time)