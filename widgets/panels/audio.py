                  

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.stack import Stack
from fabric.widgets.eventbox import EventBox
from fabric.widgets.scale import Scale
from services.bootstrap import audio_service
from fabric.utils import invoke_repeater
from widgets.common.popupmenu import PopupMenu
from utils.config import config

KNOWN_BROWSER_ICONS = {"firefox", "chrome", "chromium", "brave", "edge"}

def resolve_stream_display(stream):
    display_name = stream.name
    icon_name = (
        stream.icon_name if getattr(stream, "icon_name", None) else "audio-x-generic"
    )
    desc = getattr(stream, "description", None)
    if desc and desc != "AudioStream" and desc != display_name:
        display_name = desc
        desc_lower = desc.lower()
        if "youtube" in desc_lower:
            icon_name = "youtube"
        elif "spotify" in desc_lower:
            icon_name = "spotify"
        elif stream.name and stream.name.lower() in KNOWN_BROWSER_ICONS:
            icon_name = stream.name.lower()
    return display_name, icon_name


class AudioPanel(Box):
    def __init__(self, parent_window, **kwargs):
        super().__init__(
            orientation="v", spacing=10, name="controlcenter-panel-container", **kwargs
        )
        self.parent_window = parent_window
        self.audio = audio_service
        self.setup_state()
        self.build_ui()
        self.connect_signals()
        self.update_ui()

    def setup_state(self):
        self._lock = False
        self._last_total = 0
        self._speaker_mute_handler = None
        self._bound_speaker = None
        
    def build_ui(self):
        self.stream_list = Box(orientation="v", spacing=10, h_expand=True)
        self.count_label = Label(
            label="0 Streams", h_align="start", name="controlcenter-section-title"
        )
        self.mute_icon = Image(
            icon_name="audio-volume-high-symbolic",
            icon_size=config.icon_sizes[2],
        )
        self.mute_label = Label(label="Mute")
        self.mute_btn = Button(
            child=Box(children=[self.mute_icon, self.mute_label], spacing=5),
            on_clicked=self.on_mute_clicked,
            name="controlcenter-btn",
        )
        self.header = Box(
            children=[self.count_label, Box(h_expand=True), self.mute_btn],
            h_expand=True,
            name="controlcenter-panel-header",
        )
        self.empty_placeholder = Box(
            orientation="v",
            v_align="center",
            h_align="center",
            spacing=10,
            v_expand=True,
            children=[
                Image(
                    icon_name="audio-speakers-symbolic",
                    icon_size=config.icon_sizes[6],
                ),
                Label(
                    label="Audio streams will appear here",
                    name="controlcenter-empty-label",
                ),
            ],
        )
        self.app_scroll = ScrolledWindow(
            child=self.stream_list,
            h_expand=True,
            v_expand=True,
            h_scrollbar_policy="never",
            overlay_scroll=True,
            name="controlcenter-scrollable",
        )
        self.stream_stack = Stack(
            transition_type="crossfade", transition_duration=300, v_expand=True
        )
        self.stream_stack.add_named(self.app_scroll, "list")
        self.stream_stack.add_named(self.empty_placeholder, "empty")
        self.hardware_controls = Box(
            orientation="v", spacing=5, name="controlcenter-audio-hw-fixed"
        )

        self.output_active_row = Box(name="controlcenter-audio-fixed-row")
        self.input_active_row = Box(name="controlcenter-audio-fixed-row")
        self.hardware_controls.add(self.output_active_row)
        self.hardware_controls.add(self.input_active_row)
        self.add(self.header)
        self.add(self.stream_stack)
        self.add(self.hardware_controls)

    def connect_signals(self):
        self.audio.connect("changed", self.on_audio_changed)
        self.audio.connect("notify::speaker", lambda *_: GLib.idle_add(self.update_ui))
        self.audio.connect(
            "notify::microphone", lambda *_: GLib.idle_add(self.update_ui)
        )

    def bind_speaker(self):
        speaker = self.audio.speaker
        if self._bound_speaker is speaker:
            return
        if self._bound_speaker is not None and self._speaker_mute_handler is not None:
            try:
                self._bound_speaker.disconnect(self._speaker_mute_handler)
            except Exception:
                pass
        self._bound_speaker = speaker
        self._speaker_mute_handler = None
        if speaker is not None:
            self._speaker_mute_handler = speaker.connect(
                "notify::muted", lambda *_: GLib.idle_add(self.update_mute_button)
            )

    def update_mute_button(self, *_):
        speaker = self.audio.speaker
        has_speaker = speaker is not None
        self.mute_btn.set_sensitive(has_speaker)
        muted = bool(has_speaker and speaker.muted)
        self.mute_icon.set_from_icon_name(
            "audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic",
            config.icon_sizes[2],
        )
        self.mute_label.set_label("Unmute" if muted else "Mute")
        return False

    def on_mute_clicked(self, *_):
        if self.audio.speaker is None:
            return
        self.audio.speaker.muted = not self.audio.speaker.muted
        self.update_mute_button()

    def on_audio_changed(self, *args):
        total = (
            len(self.audio.applications)
            + len(self.audio.recorders)
            + len(self.audio.speakers)
            + len(self.audio.microphones)
        )
        if self._last_total != total:
            self._last_total = total
            GLib.idle_add(self.update_ui)

    def update_ui(self, *args):
        if self._lock:
            return
        self._lock = True
        for c in [self.stream_list, self.output_active_row, self.input_active_row]:
            for child in c.get_children():
                c.remove(child)
        streams = list(self.audio.applications) + list(self.audio.recorders)
        self.count_label.set_label(
            f"{len(streams)} Stream{'s' if len(streams) != 1 else ''} Playing"
        )
        for app in streams:
            self.stream_list.add(StreamWidget(app))
        if self.audio.speaker:
            self.output_active_row.add(
                self.create_device_row(self.audio.speaker, "speaker")
            )

        if self.audio.microphone:
            self.input_active_row.add(
                self.create_device_row(self.audio.microphone, "microphone")
            )
        else:
            no_mic_label = Label(
                label="No input device detected",
                h_align="center",
                name="controlcenter-status-label",
                h_expand=True,
            )
            self.input_active_row.add(
                Box(
                    children=[no_mic_label],
                    h_expand=True,
                    v_align="center",
                    h_align="center",
                    style="padding: 10px;",
                )
            )
        self.bind_speaker()
        self.update_mute_button()
        has_streams = bool(streams)
        self.stream_stack.set_visible_child_name("list" if has_streams else "empty")
        self.show_all()
        self._lock = False

    def create_device_row(self, device, dev_type):
        return ActiveDeviceWidget(device, self.parent_window, dev_type)


class StreamWidget(Box):
    def __init__(self, stream, **kwargs):
        super().__init__(
            spacing=10, name="controlcenter-audio-item", h_expand=True, **kwargs
        )
        self.stream = stream
        self._dragging = False
        self.icon = Image(icon_size=config.icon_sizes[4])
        self.name_label = Label(
            h_align="start",
            h_expand=True,
            ellipsize="end",
            max_chars_width=37,
            line_wrap="word-char",
        )
        self.volume_slider = Scale(
            value=stream.volume,
            min_value=0,
            max_value=100,
            on_value_changed=self.on_volume_change,
            h_expand=True,
            name="controlcenter-slider",
        )
        self.volume_slider.connect("button-press-event", self.on_drag_start)
        self.volume_slider.connect("button-release-event", self.on_drag_end)
        stream.connect("notify::volume", self.on_stream_volume_notify)
        stream.connect("changed", self.on_stream_changed)
        self.add(self.icon)
        self.add(
            Box(
                orientation="v",
                h_expand=True,
                children=[self.name_label, self.volume_slider],
            )
        )
        self.refresh_ui()

    def on_drag_start(self, *args):
        self._dragging = True
        return False

    def on_drag_end(self, *args):
        self._dragging = False
        return False

    def on_volume_change(self, s):
        if abs(s.value - self.stream.volume) > 1:
            self.stream.volume = s.value

    def on_stream_volume_notify(self, *args):
        if (
            not self._dragging
            and abs(self.volume_slider.value - self.stream.volume) > 1
        ):
            self.volume_slider.set_value(self.stream.volume)

    def on_stream_changed(self, *args):
        GLib.idle_add(self.refresh_ui)

    def refresh_ui(self):
        display_name, icon_name = resolve_stream_display(self.stream)
        self.name_label.set_label(display_name)
        self.icon.set_from_icon_name(icon_name, config.icon_sizes[4])
        return False


class ActiveDeviceWidget(EventBox):
    def __init__(self, device, parent_window, dev_type, **kwargs):
        super().__init__(events=["button-press"], h_expand=True, **kwargs)
        self.device = device
        self._dragging = False
        self.parent_window = parent_window
        self.dev_type = dev_type
        container = Box(spacing=10, h_expand=True)
        icon_name = (
            "audio-speakers-symbolic"
            if dev_type == "speaker"
            else "audio-input-microphone-symbolic"
        )
        self.icon = Image(icon_name=icon_name, icon_size=config.icon_sizes[4])
        self.slider = Scale(
            value=device.volume,
            min_value=0,
            max_value=100,
            on_value_changed=self.on_volume_change,
            h_expand=True,
            name="controlcenter-slider",
        )
        self.slider.connect("button-press-event", self.on_drag_start)
        self.slider.connect("button-release-event", self.on_drag_end)
        device.connect("changed", self.on_device_changed)
        device.connect("notify::muted", lambda *_: self.on_device_changed())

        self.arrow_icon = Image(
            icon_name="pan-down-symbolic", icon_size=config.icon_sizes[0]
        )
        arrow_box = Box(children=[self.arrow_icon], v_align="center")

        container.add(self.icon)
        container.add(self.slider)
        container.add(arrow_box)
        self.add(container)

        self.popup = None
        invoke_repeater(100, self.setup_popup, initial_call=False)
        self.connect("button-press-event", self.toggle_popup)
        self.connect("destroy", self.on_destroy)

    def setup_popup(self):
        parent = self.get_parent()
        if not parent:
            return True
        width = parent.get_allocated_width()
        if width > 1:
            self.popup = PopupMenu(
                parent=self.parent_window,
                pointing_to=parent,
                size=(width, -1),
                alignment="bottom",
                name_prefix="audio",
                visible_items=5,
            )
            self.rebuild_popup_items()
            self.popup.revealer.connect("notify::reveal-child", self.on_popup_revealed)
            return False
        return True

    def rebuild_popup_items(self):
        if not self.popup:
            return
        self.popup.remove_all_items()
        audio = audio_service
        devices = audio.speakers if self.dev_type == "speaker" else audio.microphones
        current_device = (
            audio.speaker if self.dev_type == "speaker" else audio.microphone
        )
        current_id = current_device.id if current_device else None
        for d in devices:
            self.popup.add_item(
                DeviceWidget(
                    d,
                    audio,
                    self.dev_type,
                    popup=self.popup,
                    selected=d.id == current_id,
                )
            )

    def on_popup_revealed(self, revealer, *args):
        is_revealed = revealer.get_reveal_child()
        self.arrow_icon.set_from_icon_name(
            "pan-up-symbolic" if is_revealed else "pan-down-symbolic",
            config.icon_sizes[0],
        )

    def toggle_popup(self, widget, event):
        if event.window == widget.get_window():
            if self.popup:
                if self.popup.revealer.get_reveal_child():
                    self.popup.unreveal()
                else:
                    self.rebuild_popup_items()
                    self.popup.reveal()
        return False

    def on_destroy(self, *args):
        if self.popup:
            self.popup.destroy()

    def on_drag_start(self, *args):
        self._dragging = True
        return False

    def on_drag_end(self, *args):
        self._dragging = False
        return False

    def on_volume_change(self, s):
        if abs(s.value - self.device.volume) > 1:
            self.device.volume = s.value

    def on_device_changed(self, *args):
        if not self._dragging and abs(self.slider.value - self.device.volume) > 1:
            self.slider.set_value(self.device.volume)
        if self.device.muted:
            self.add_style_class("muted")
            self.slider.add_style_class("muted")
        else:
            self.remove_style_class("muted")
            self.slider.remove_style_class("muted")


class DeviceWidget(EventBox):
    def __init__(
        self, device, audio_service, device_type, popup, selected=False, **kwargs
    ):
        super().__init__(
            events=["button-press", "enter-notify", "leave-notify"],
            name="audio-popup-item",
            **kwargs,
        )
        self.device = device
        self.selected = selected

        container = Box(spacing=10, h_expand=True)
        self.connect(
            "button-press-event", self.on_row_clicked, audio_service, device_type, popup
        )
        self.connect("enter-notify-event", lambda *_: self.add_style_class("hovered"))
        self.connect(
            "leave-notify-event", lambda *_: self.remove_style_class("hovered")
        )

        name = Label(
            label=device.description or device.name,
            h_align="start",
            h_expand=True,
            line_wrap="word-char",
        )
        indicator = Image(
            icon_name="object-select-symbolic", icon_size=config.icon_sizes[1]
        )
        indicator.set_no_show_all(True)
        indicator.set_halign(Gtk.Align.END)
        indicator.set_valign(Gtk.Align.CENTER)
        indicator_box = Box(h_align="end", v_align="center", size=(18, -1))
        indicator_box.set_margin_end(4)
        indicator_box.add(indicator)
        if not selected:
            indicator.hide()
        else:
            indicator.show()
        container.add(name)
        container.add(indicator_box)
        self.add(container)
        if selected:
            self.add_style_class("active")

    def on_row_clicked(self, widget, event, audio_service, device_type, popup):
        if event.window == widget.get_window():
            if device_type == "speaker":
                audio_service._control.set_default_sink(self.device.stream)
            else:
                audio_service._control.set_default_source(self.device.stream)
            if popup:
                popup.unreveal()
        return False
