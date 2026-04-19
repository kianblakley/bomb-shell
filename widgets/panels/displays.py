                  

import gi
import re
import subprocess

gi.require_version("Gtk", "3.0")
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.scale import Scale
from fabric.utils import invoke_repeater
from services.bootstrap import niri_service
from utils.config import config
from widgets.common.popupmenu import PopupMenu


class DisplaysPanel(Box):
    def __init__(self, parent_window, **kwargs):
        super().__init__(
            orientation="v", spacing=10, name="controlcenter-panel-container", **kwargs
        )
        self.parent_window = parent_window
        self.build_ui()
        self.update_list()

    def build_ui(self):
        self.count_label = Label(
            label="", h_align="start", name="controlcenter-section-title"
        )
        self.refresh_btn = Button(
            child=Box(
                children=[
                    Image(
                        icon_name="view-refresh-symbolic",
                        icon_size=config.icon_sizes[2],
                    ),
                    Label(label="Refresh"),
                ],
                spacing=5,
            ),
            on_clicked=lambda *_: self.update_list(),
            name="controlcenter-btn",
        )
        self.header = Box(
            children=[self.count_label, Box(h_expand=True), self.refresh_btn],
            h_expand=True,
            name="controlcenter-panel-header",
        )
        self.display_list = Box(orientation="v", spacing=10)
        self.add(self.header)
        self.add(
            ScrolledWindow(
                child=self.display_list,
                h_expand=True,
                v_expand=True,
                h_scrollbar_policy="never",
                overlay_scroll=True,
                name="controlcenter-scrollable",
            )
        )

    def update_list(self):
        for c in self.display_list.get_children():
            self.display_list.remove(c)
        outputs = niri_service.get_outputs()
        self.count_label.set_label(
            f"{len(outputs)} Display{'s' if len(outputs) != 1 else ''} Connected"
        )
        for output_info in outputs:
            self.display_list.add(DisplayWidget(output_info, self.parent_window))
        self.show_all()


class DisplayWidget(Box):
    def __init__(self, output_info, parent_window, **kwargs):
        super().__init__(
            orientation="v", spacing=10, name="controlcenter-list-item", **kwargs
        )
        self.output_id = output_info["id"]
        self.parent_window = parent_window
        self.mode_popup = None
        self.scale_popup = None
        self.build_ui(output_info)
        self.connect_signals()
        invoke_repeater(
            100, self.setup_popups, output_info["modes"], initial_call=False
        )

    def build_ui(self, output_info):
        icon = Image(
            icon_name="video-display", icon_size=config.icon_sizes[4]
        )
        name = Label(
            label=f"{output_info['name']} ({output_info['id']})",
            h_align="start",
            h_expand=True,
            max_chars_width=36,
            line_wrap="word-char",
        )
        header = Box(spacing=10)
        header.add(icon)
        header.add(name)
        self.add(header)
        self.brightness_slider = Scale(
            min_value=0,
            max_value=100,
            value=self.get_brightness(),
            on_value_changed=lambda s: self.set_brightness(s.value),
            h_expand=True,
            name="controlcenter-slider",
        )
        self.add(
            Box(
                orientation="v",
                spacing=5,
                children=[
                    Label(
                        label="Brightness",
                        h_align="start",
                        name="controlcenter-status-label",
                    ),
                    self.brightness_slider,
                ],
            )
        )
        info = Box(spacing=10)
        info.add(
            Label(
                label=f"Mode: {output_info['current_mode']}",
                h_align="start",
                name="controlcenter-status-label",
            )
        )
        info.add(
            Label(
                label=f"Scale: {output_info['current_scale']}",
                h_align="start",
                name="controlcenter-status-label",
            )
        )
        self.add(info)
        btns = Box(spacing=10)
        self.mode_button = Button(
            label="Modes", h_expand=True, name="controlcenter-btn"
        )
        self.scale_button = Button(
            label="Scale", h_expand=True, name="controlcenter-btn"
        )
        btns.add(self.mode_button)
        btns.add(self.scale_button)
        self.add(btns)

    def connect_signals(self):
        self.mode_button.connect(
            "clicked", lambda *_: self.toggle_popup(self.mode_popup)
        )
        self.scale_button.connect(
            "clicked", lambda *_: self.toggle_popup(self.scale_popup)
        )

    def setup_popups(self, modes):
        mode_button_width = self.mode_button.get_allocated_width()
        scale_button_width = self.scale_button.get_allocated_width()
        if mode_button_width > 1 and scale_button_width > 1:
            self.mode_popup = PopupMenu(
                parent=self.parent_window,
                pointing_to=self.mode_button,
                size=(mode_button_width, -1),
                visible_items=5,
            )
            for x in modes:
                display_label = re.sub(r"\(.*?\)", "", x).strip()
                display_label = re.sub(r"(\.\d\d)\d+", r"\1", display_label)
                btn = Button(
                    label=display_label,
                    h_align="fill",
                    h_expand=True,
                    name="displays-popup-item",
                )
                btn.connect(
                    "clicked",
                    lambda *_, val=x: (
                        niri_service.set_mode(self.output_id, val),
                        self.mode_popup.unreveal(),
                    ),
                )
                self.mode_popup.add_item(btn)

            self.scale_popup = PopupMenu(
                parent=self.parent_window,
                pointing_to=self.scale_button,
                size=(scale_button_width, -1),
                visible_items=5,
            )
            for x in [1.0, 1.25, 1.5, 1.75, 2.0, 2.25]:
                btn = Button(
                    label=f"{x}x",
                    h_align="fill",
                    h_expand=True,
                    name="displays-popup-item",
                )
                btn.connect(
                    "clicked",
                    lambda *_, val=x: (
                        niri_service.set_scale(self.output_id, val),
                        self.scale_popup.unreveal(),
                    ),
                )
                self.scale_popup.add_item(btn)
            return False
        return True

    def toggle_popup(self, popup):
        if not popup:
            return
        if popup.revealer.get_reveal_child():
            popup.unreveal()
        else:
            popup.reveal()

    def get_brightness(self):
        try:
            out = subprocess.check_output(["brightnessctl", "g"], text=True)
            max_b = subprocess.check_output(["brightnessctl", "m"], text=True)
            return (int(out) / int(max_b)) * 100
        except Exception:
            return 50

    def set_brightness(self, v):
        try:
            subprocess.run(["brightnessctl", "s", f"{int(v)}%"], check=True)
        except Exception:
            pass
