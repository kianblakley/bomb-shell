                  

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.stack import Stack
from fabric.widgets.revealer import Revealer
from fabric.widgets.eventbox import EventBox
from services.bootstrap import bluetooth_service
from utils.config import config
SCAN_DURATION_SECONDS = 12


class BluetoothPanel(Box):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="v", spacing=10, name="controlcenter-panel-container", **kwargs
        )
        self.bluetooth_client = bluetooth_service
        self.setup_state()
        self.build_ui()
        self.connect_signals()
        self.on_changed()

    def setup_state(self):
        self._scan_timeout_id = None
        self._cached_devices = {}
        self._failed_addresses = set()
        self._expanded_address = None

    def build_ui(self):
        self.scan_icon = Image(
            icon_name="system-search-symbolic", icon_size=config.icon_sizes[2]
        )
        self.scan_label = Label(label="Scan")
        self.count_label = Label(
            label="", h_align="start", name="controlcenter-section-title"
        )
        self.scan_btn = Button(
            child=Box(
                children=[
                    self.scan_icon,
                    self.scan_label,
                ],
                spacing=5,
            ),
            on_clicked=self.on_scan_clicked,
            name="controlcenter-btn",
        )
        self.header = Box(
            children=[self.count_label, Box(h_expand=True), self.scan_btn],
            h_expand=True,
            name="controlcenter-panel-header",
        )
        self.device_list = Box(orientation="v", spacing=10)
        self.empty_placeholder = Box(
            orientation="v",
            v_align="center",
            h_align="center",
            spacing=10,
            v_expand=True,
            children=[
                Image(
                    icon_name="bluetooth-active-symbolic",
                    icon_size=config.icon_sizes[6],
                ),
                Label(
                    label="Press scan to search for nearby devices",
                    name="controlcenter-empty-label",
                ),
            ],
        )
        self.list_scroll = ScrolledWindow(
            child=self.device_list,
            h_expand=True,
            v_expand=True,
            h_scrollbar_policy="never",
            overlay_scroll=True,
            name="controlcenter-scrollable",
        )
        self.list_stack = Stack(
            transition_type="crossfade", transition_duration=300, v_expand=True
        )
        self.list_stack.add_named(self.list_scroll, "list")
        self.list_stack.add_named(self.empty_placeholder, "empty")
        self.enabled_content = Box(orientation="v", spacing=10, v_expand=True)
        self.enabled_content.add(self.header)
        self.enabled_content.add(self.list_stack)
        self.stack = Stack(
            transition_type="crossfade", transition_duration=300, v_expand=True
        )
        self.disabled_content = Box(
            orientation="v",
            v_align="center",
            h_align="center",
            spacing=10,
            children=[
                Image(
                    icon_name="bluetooth-disabled-symbolic",
                    icon_size=config.icon_sizes[6],
                ),
                Label(label="Bluetooth is off"),
            ],
        )
        self.stack.add_named(self.enabled_content, "on")
        self.stack.add_named(self.disabled_content, "off")
        self.add(self.stack)

    def connect_signals(self):
        self.connect("button-press-event", self.on_bg_clicked)
        self.bluetooth_client.connect("changed", self.on_changed)

    def on_tab_selected(self):
        return

    def on_scan_clicked(self, *_):
        if self.bluetooth_client.scanning:
            self.stop_scan()
            return
        self.start_scan()

    def start_scan(self):
        if not self.bluetooth_client.powered:
            return
        self.prune_cached_devices()
        if self._scan_timeout_id is not None:
            GLib.source_remove(self._scan_timeout_id)
            self._scan_timeout_id = None
        GLib.idle_add(self.begin_scan)

    def stop_scan(self):
        if self._scan_timeout_id is not None:
            GLib.source_remove(self._scan_timeout_id)
            self._scan_timeout_id = None
        if self.bluetooth_client.scanning:
            self.bluetooth_client.scanning = False
        self.on_changed()

    def begin_scan(self):
        if not self.bluetooth_client.powered:
            return False
        self.bluetooth_client.scanning = True
        self._scan_timeout_id = GLib.timeout_add_seconds(
            SCAN_DURATION_SECONDS,
            self.end_scan,
        )
        self.on_changed()
        return False

    def end_scan(self):
        self._scan_timeout_id = None
        if self.bluetooth_client.scanning:
            self.bluetooth_client.scanning = False
        self.on_changed()
        return False

    def prune_cached_devices(self):
        self._cached_devices = {
            address: device
            for address, device in self._cached_devices.items()
            if device.connected or device.paired
        }
        self._failed_addresses = {
            address
            for address in self._failed_addresses
            if address in self._cached_devices
        }

    def device_sort_key(self, device):
        return (
            not device.connected,
            not device.connecting,
            not device.paired,
            (device.alias or device.name or "").lower(),
        )

    def on_connect_requested(self, device):
        if device.connecting or device.connected:
            return
        self._failed_addresses.discard(device.address)
        device._connecting = True
        device.notifier("connecting")
        self.bluetooth_client.connect_device(
            device,
            True,
            lambda success, device=device: self.on_connect_finished(device, success),
        )

    def on_connect_finished(self, device, success):
        device._connecting = False
        if success:
            self._failed_addresses.discard(device.address)
        else:
            self._failed_addresses.add(device.address)
        device.notifier("connecting")
        device.notifier("connected")
        self.on_changed()

    def on_changed(self, *args):
        powered = self.bluetooth_client.powered
        self.stack.set_visible_child_name("on" if powered else "off")
        if not powered:
            if self._scan_timeout_id is not None:
                GLib.source_remove(self._scan_timeout_id)
                self._scan_timeout_id = None
            if self.bluetooth_client.scanning:
                self.bluetooth_client.scanning = False
        self.update_scan_button()
        for device in self.bluetooth_client.devices:
            self._cached_devices[device.address] = device
            if device.connected or device.connecting:
                self._failed_addresses.discard(device.address)
        visible_devices = sorted(
            self._cached_devices.values(), key=self.device_sort_key
        )
        count = len(visible_devices)
        if self.bluetooth_client.scanning:
            self.count_label.set_label("Scanning...")
        else:
            self.count_label.set_label(
                f"{count} Device{'s' if count != 1 else ''} Available"
            )
        for c in self.device_list.get_children():
            self.device_list.remove(c)
        for d in visible_devices:
            self.device_list.add(
                BluetoothDeviceWidget(
                    d,
                    failed=d.address in self._failed_addresses,
                    on_connect=self.on_connect_requested,
                    expanded=d.address == self._expanded_address,
                    on_toggle=self.on_device_toggled,
                )
            )
        self.list_stack.set_visible_child_name("list" if visible_devices else "empty")
        self.show_all()

    def update_scan_button(self):
        scanning = bool(
            self.bluetooth_client.scanning and self.bluetooth_client.powered
        )
        self.scan_icon.set_from_icon_name(
            "process-stop-symbolic" if scanning else "system-search-symbolic",
            config.icon_sizes[2],
        )
        self.scan_label.set_label("Stop" if scanning else "Scan")

    def on_device_toggled(self, address, expanded):
        self._expanded_address = address if expanded else None
        if not expanded:
            return
        for child in self.device_list.get_children():
            if (
                getattr(child, "device", None)
                and child.device.address != address
                and hasattr(child, "set_expanded")
            ):
                child.set_expanded(False)

    def toggle_power(self):
        self.bluetooth_client.powered = not self.bluetooth_client.powered

    def on_bg_clicked(self, widget, event):
        from widgets.panels.displays import DisplayWidget

        DisplayWidget.close_active_popup()
        return False


class BluetoothDeviceWidget(Box):
    def __init__(
        self,
        device,
        failed=False,
        on_connect=None,
        expanded=False,
        on_toggle=None,
        **kwargs,
    ):
        super().__init__(spacing=0, orientation="v", **kwargs)
        self.device = device
        self.failed = failed
        self.on_connect = on_connect
        self.on_toggle = on_toggle
        self._expanded = False
        self.wrapper = EventBox(
            events=["button-press"],
            name="controlcenter-list-item",
        )
        self.wrapper.set_hexpand(True)
        self.wrapper.connect("button-press-event", self.on_row_clicked)
        self.add(self.wrapper)

        content = Box(orientation="v", style="padding: 10px;")
        self.wrapper.add(content)

        main_row = Box(spacing=10, h_expand=True)
        icon_name = device.icon_name or "bluetooth"
        if device.type in ["Speakers", "Audio"]:
            icon_name = "audio-speakers"
        elif device.type == "Headphones":
            icon_name = "audio-headphones"
        elif device.type == "Headset":
            icon_name = "audio-headset"
        main_row.add(
            Image(icon_name=icon_name, icon_size=config.icon_sizes[4])
        )
        text_box = Box(orientation="v", spacing=4, h_expand=True)
        header_row = Box(spacing=10, h_expand=True)
        header_row.add(
            Label(
                label=device.alias or device.name,
                h_align="start",
                h_expand=True,
                ellipsize="end",
                max_chars_width=20,
            )
        )
        status_text = self.get_status_text()
        if status_text:
            header_row.add(
                Label(
                    label=status_text, h_align="end", name="controlcenter-status-label"
                )
            )
        text_box.add(header_row)

        self.arrow_icon = Image(
            icon_name="pan-down-symbolic", icon_size=config.icon_sizes[0]
        )
        detail_row = Box(spacing=10, h_expand=True)
        content.add(main_row)
        detail_text = self.get_detail_text()
        if detail_text:
            detail_row.add(
                Label(
                    label=detail_text,
                    h_align="start",
                    h_expand=True,
                    name="controlcenter-status-label",
                )
            )
        else:
            detail_row.add(Box(h_expand=True))
        detail_row.add(Box(children=[self.arrow_icon], h_align="end"))
        text_box.add(detail_row)
        main_row.add(text_box)
        action_row = Box(spacing=5, h_expand=True, name="controlcenter-action-row")
        action_row.add(Box(h_expand=True))
        if self.device.connected:
            self.action_btn = Button(
                label="Disconnect",
                on_clicked=self.on_disconnect_clicked,
                name="controlcenter-btn",
            )
        else:
            self.action_btn = Button(
                label="Connect",
                on_clicked=self.on_connect_clicked,
                name="controlcenter-btn",
            )
        if self.device.connecting:
            self.action_btn.set_sensitive(False)
        action_row.add(self.action_btn)
        self.action_revealer = Revealer(
            child=action_row, transition_type="slide-down", transition_duration=200
        )
        content.add(self.action_revealer)
        self.set_expanded(expanded, notify=False)

    def get_status_text(self):
        if self.device.connecting:
            return "Connecting..."
        if self.device.connected:
            return "Connected"
        if self.failed:
            return "Failed"
        if self.device.paired:
            return "Paired"
        return None

    def get_detail_text(self):
        if not self.device.type:
            return None
        return " ".join(self.device.type.split())

    def set_expanded(self, expanded, notify=True):
        self._expanded = expanded
        if expanded:
            self.action_revealer.reveal()
        else:
            self.action_revealer.unreveal()
        self.arrow_icon.set_from_icon_name(
            "pan-up-symbolic" if expanded else "pan-down-symbolic",
            config.icon_sizes[0],
        )
        if notify and self.on_toggle:
            self.on_toggle(self.device.address, expanded)

    def on_row_clicked(self, widget, event):
        if event.window != widget.get_window():
            return False
        self.set_expanded(not self._expanded)
        return False

    def on_connect_clicked(self, *_):
        if self.device.connecting or self.device.connected:
            return
        if self.on_connect:
            self.on_connect(self.device)
        self.set_expanded(False)

    def on_disconnect_clicked(self, *_):
        self.device.connected = False
        self.set_expanded(False)
        return False
