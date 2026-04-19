                  

from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.revealer import Revealer
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GtkLayerShell, GLib


class PopupMenu(WaylandWindow):
    _active_popups = []

    def __init__(
        self,
        parent: WaylandWindow,
        pointing_to: Gtk.Widget | None = None,
        margin: tuple[int, ...] | str = "0px 0px 0px 0px",
        transition_duration: int = 250,
        alignment: str = "top",
        name_prefix: str = "displays",
        visible_items: int | None = None,
        **kwargs,
    ):
        self._parent = parent
        self._pointing_widget = pointing_to
        self._base_margin = self.extract_margin(margin)
        self._alignment = alignment
        self._name_prefix = name_prefix
        self._visible_items = visible_items

                                            
        self._requested_size = kwargs.get("size", (-1, -1))
        if "size" in kwargs:
            del kwargs["size"]

        super().__init__(visible=False, **kwargs)
        PopupMenu._active_popups.append(self)

                                                                              
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)

        self.exclusivity = "none"

        self.inner_box = Box(
            orientation="v",
            spacing=2,
            name=f"{self._name_prefix}-popup-content",
            h_expand=True,
        )

        min_width = self._requested_size[0] if self._requested_size[0] > 0 else -1
        max_height = self._requested_size[1] if self._requested_size[1] > 0 else 200

        self.scrolled_window = ScrolledWindow(
            child=self.inner_box,
            min_content_size=(min_width, max_height),
            max_content_size=(-1, max_height),
            propagate_natural_height=True,
            h_scrollbar_policy="never",
            v_scrollbar_policy="automatic",
            overlay_scroll=True,
            name="controlcenter-scrollable",
            h_expand=True,
        )
        self.outer_box = Box(
            name=f"{self._name_prefix}-popup-outer",
            children=[self.scrolled_window],
            h_expand=True,
        )

        transition_type = "slide-up" if self._alignment == "bottom" else "slide-down"
        self.revealer = Revealer(
            child=self.outer_box,
            transition_type=transition_type,
            transition_duration=transition_duration,
            h_expand=True,
        )
        self.root_box = Box(
            name=f"{self._name_prefix}-popup-root",
            children=[self.revealer],
            size=1,
            h_expand=True,
        )

        self.add(self.root_box)

                                                                                  
        self.do_calculate_edges()

        self.margin = self._base_margin.values()
        self.connect("notify::visible", self.do_update_handlers)

        self._gesture = None
        if self._parent:
            self._gesture = Gtk.GestureMultiPress.new(self._parent)
            self._gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            self._gesture.connect("pressed", self.on_parent_pressed)

        self.connect("destroy", self.on_destroy)

    def on_parent_pressed(self, gesture, n_press, x, y):
        if self.revealer.get_reveal_child():
            if self._pointing_widget:
                alloc = self._pointing_widget.get_allocation()
                coords = self._pointing_widget.translate_coordinates(self._parent, 0, 0)
                if coords:
                    px, py = coords
                    if px <= x <= px + alloc.width and py <= y <= py + alloc.height:
                        return
            self.unreveal()

    def on_destroy(self, *args):
        if self in PopupMenu._active_popups:
            PopupMenu._active_popups.remove(self)

    @classmethod
    def clear_all(cls):
        for popup in cls._active_popups:
            if popup.get_visible():
                popup.revealer.set_reveal_child(False)
                popup.hide()

    def add_item(self, widget: Gtk.Widget):
        self.inner_box.add(widget)
        widget.show_all()

    def remove_all_items(self):
        for child in self.inner_box.get_children():
            self.inner_box.remove(child)

    def update_height(self):
        if not self._visible_items:
            return

        children = self.inner_box.get_children()
        if not children:
            self.scrolled_window.set_min_content_height(-1)
            self.scrolled_window.set_max_content_height(-1)
            return False

        available_width = self.inner_box.get_allocated_width()
        if (
            available_width <= 1
            and self._requested_size
            and self._requested_size[0] > 0
        ):
            available_width = self._requested_size[0]

        if available_width <= 1:
            GLib.idle_add(self.update_height)
            return False

        spacing = self.inner_box.get_spacing()
        num_items = min(self._visible_items, len(children))

        total_height = 0
        for child in children[:num_items]:
            _, natural_height = child.get_preferred_height_for_width(available_width)
            if natural_height <= 0:
                GLib.idle_add(self.update_height)
                return False
            total_height += natural_height
        total_height += spacing * max(0, num_items - 1)

        self.scrolled_window.set_min_content_height(total_height)
        self.scrolled_window.set_max_content_height(total_height)
        return False

    def schedule_height_updates(self):
        if not self._visible_items:
            return
        self.update_height()
        GLib.idle_add(self.update_height)
        for delay in (30, 80, 150):
            GLib.timeout_add(delay, self.update_height)

    def reveal(self):
        self.show_all()
        if self._visible_items:
            self.schedule_height_updates()
        GLib.idle_add(lambda: self.revealer.set_reveal_child(True))

    def unreveal(self):
        self.revealer.set_reveal_child(False)
        duration = (
            self.revealer.transition_duration
            if hasattr(self.revealer, "transition_duration")
            else 250
        )
        GLib.timeout_add(duration + 50, lambda: (self.hide(), False)[1])

    def get_coords_for_widget(self, widget: Gtk.Widget) -> tuple[int, int]:
        if not ((toplevel := widget.get_toplevel()) and toplevel.is_toplevel()):                
            return 0, 0
        x, y = widget.translate_coordinates(toplevel, 0, 0) or (
            0,
            0,
        )
        return round(x), round(y)

    def set_pointing_to(self, widget: Gtk.Widget | None):
        if self._pointing_widget:
            try:
                self._pointing_widget.disconnect_by_func(self.do_handle_size_allocate)
            except Exception:
                pass
        self._pointing_widget = widget
        return self.do_update_handlers()

    def do_update_handlers(self, *_):
        if not self._pointing_widget:
            return

        if not self.get_visible():
            try:
                self._pointing_widget.disconnect_by_func(self.do_handle_size_allocate)
                self.disconnect_by_func(self.do_handle_size_allocate)
            except Exception:
                pass
            return

        self._pointing_widget.connect("size-allocate", self.do_handle_size_allocate)
        self.connect("size-allocate", self.do_handle_size_allocate)

        return self.do_handle_size_allocate()

    def do_handle_size_allocate(self, *_):
        return self.do_reposition(self.do_calculate_edges())

    def set_anchor_direct(self, edges: list[GtkLayerShell.Edge]):
        for edge in [
            GtkLayerShell.Edge.TOP,
            GtkLayerShell.Edge.RIGHT,
            GtkLayerShell.Edge.BOTTOM,
            GtkLayerShell.Edge.LEFT,
        ]:
            GtkLayerShell.set_anchor(self, edge, edge in edges)

    def do_calculate_edges(self):
        parent_anchor = self._parent.anchor

        edge_y = (
            GtkLayerShell.Edge.BOTTOM
            if self._alignment == "bottom"
            else GtkLayerShell.Edge.TOP
        )

        if (
            GtkLayerShell.Edge.RIGHT in parent_anchor
            and GtkLayerShell.Edge.LEFT not in parent_anchor
        ):
            self.set_anchor_direct([edge_y, GtkLayerShell.Edge.RIGHT])
            return "overlay-right"
        else:
            self.set_anchor_direct([edge_y, GtkLayerShell.Edge.LEFT])
            return "overlay-left"

    def do_reposition(self, layout: str):
        if self._requested_size:
            if self._requested_size[0] > 0:
                self.set_size_request(self._requested_size[0], -1)

        parent_margin = self._parent.margin
        parent_top, parent_right, parent_bottom, parent_left = parent_margin

        width = self.get_allocated_width()

        if self._pointing_widget:
            coords = self.get_coords_for_widget(self._pointing_widget)
            widget_width = self._pointing_widget.get_allocated_width()
            widget_height = self._pointing_widget.get_allocated_height()
            coords_centered = (
                round(coords[0] + widget_width / 2),
                round(coords[1] + widget_height / 2),
            )
        else:
            coords = (0, 0)
            widget_width = self._parent.get_allocated_width()
            widget_height = self._parent.get_allocated_height()
            coords_centered = (round(widget_width / 2), round(widget_height / 2))
            widget_height = 0

        top_m, right_m, bottom_m, left_m = 0, 0, 0, 0

        if layout == "overlay-right":
            if self._alignment == "top":
                top_m = parent_top + coords[1] + widget_height
            else:
                bottom_m = parent_bottom + (
                    self._parent.get_allocated_height() - coords[1]
                )
            right_m = round(
                (parent_right + self._parent.get_allocated_width() - coords_centered[0])
                - (width / 2)
            )
        else:
            if self._alignment == "top":
                top_m = parent_top + coords[1] + widget_height
            else:
                bottom_m = parent_bottom + (
                    self._parent.get_allocated_height() - coords[1]
                )
            left_m = round((parent_left + coords_centered[0]) - (width / 2))

        self.margin = tuple(
            a + b
            for a, b in zip(
                (top_m, right_m, bottom_m, left_m),
                self._base_margin.values(),
            )
        )
