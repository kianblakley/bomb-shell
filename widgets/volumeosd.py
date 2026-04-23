from services.bootstrap import audio_service, niri_service
from fabric import Application
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.scale import Scale
from fabric.widgets.box import Box
from fabric.widgets.revealer import Revealer
from gi.repository import GLib
import math


class VolumeOSD(WaylandWindow):
    def __init__(self, **kwargs):
        super().__init__(layer="overlay", anchor="bottom", **kwargs)
        screen_size = niri_service.get_screen_size()
        self.audio = audio_service
        self.hide_timeout_id = None
        self.is_muted = None
        self._speaker = None
        self._speaker_changed_handler = None
        self.build_ui(screen_size)
        self.connect_signals()

    def build_ui(self, screen_size):
        self.slider = Scale(
            h_expand=True,
            min_value=0.0,
            max_value=100.0,
            name="volumeosd-slider",
        )
        self.slider.set_sensitive(False)

        self.osd_container = Box(
            name="volumeosd-pill",
            children=[self.slider],
            size=(math.ceil(screen_size[0] / 6), math.ceil(screen_size[1] / 20)),
        )

        self.revealer = Revealer(
            child=Box(orientation="v", children=self.osd_container),
            transition_type="slide-up",
            transition_duration=300,
        )
        self.revealer_container = Box(
            size=1,
            children=self.revealer
        )

        self.children = Box(
            children=self.revealer_container,
            name="volumeosd-revealer",
        )

    def connect_signals(self):
        self.audio.connect("notify::speaker", self.on_new_speaker)
        if self.audio.speaker:
            self.on_new_speaker()

    def on_new_speaker(self):
        if not self.audio.speaker:
            return
        if self._speaker is not None and self._speaker_changed_handler is not None:
            try:
                self._speaker.disconnect(self._speaker_changed_handler)
            except Exception:
                pass
        self._speaker = self.audio.speaker
        self.is_muted = self._speaker.muted
        self.slider.set_value(self._speaker.volume)
        self._speaker_changed_handler = self._speaker.connect(
            "changed", self.on_speaker_changed
        )

    def on_speaker_changed(self):
        if not self.audio.speaker:
            return
        if self.is_muted != self.audio.speaker.muted:
            if self.audio.speaker.muted:
                self.slider.add_style_class("muted")
                self.osd_container.add_style_class("muted")
            else:
                self.slider.remove_style_class("muted")
                self.osd_container.remove_style_class("muted")
            self.is_muted = self.audio.speaker.muted
            self.make_visible()
        elif self.slider.get_value() != self.audio.speaker.volume:
            self.slider.set_value(self.audio.speaker.volume)
            self.make_visible()

    def make_visible(self):
        self.revealer.reveal()
        if self.hide_timeout_id:
            GLib.source_remove(self.hide_timeout_id)
        self.hide_timeout_id = GLib.timeout_add(
            1500, lambda: self.revealer.unreveal() or False
        )


if __name__ == "__main__":
    volumeosd = VolumeOSD()
    app = Application("volumeosd", volumeosd)
    from utils.config import config

    app.set_stylesheet_from_file(config.style_sheet.with_name("volumeosd.css"))
    app.run()
