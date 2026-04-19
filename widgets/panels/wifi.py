                  

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.stack import Stack
from fabric.widgets.revealer import Revealer
from fabric.widgets.eventbox import EventBox
from services.bootstrap import network_service
from utils.config import config


class WifiPanel(Box):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="v", spacing=10, name="controlcenter-panel-container", **kwargs
        )
        self.network_client = network_service
        self.setup_state()
        self.build_ui()
        self.connect_signals()

    def setup_state(self):
        self.wifi_device = None
        self._connecting_bssid = None
        self._expanded_bssid = None
        self._update_pending = False
        self._force_full_refresh = False
        self._manual_scan_timeout_id = None

    def build_ui(self):
        self.count_label = Label(
            label="Searching...", h_align="start", name="controlcenter-section-title"
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
            on_clicked=self.on_refresh_clicked,
            name="controlcenter-btn",
        )
        self.header = Box(
            children=[self.count_label, Box(h_expand=True), self.refresh_btn],
            h_expand=True,
            name="controlcenter-panel-header",
        )
        self.ap_list = Box(orientation="v", spacing=10)
        self.empty_placeholder = Box(
            orientation="v",
            v_align="center",
            h_align="center",
            spacing=10,
            v_expand=True,
            children=[
                Image(
                    icon_name="network-wireless-symbolic",
                    icon_size=config.icon_sizes[6],
                ),
                Label(
                    label="Available networks will appear here",
                    name="controlcenter-empty-label",
                ),
            ],
        )
        self.list_scroll = ScrolledWindow(
            child=self.ap_list,
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
                    icon_name="network-wireless-offline-symbolic",
                    icon_size=config.icon_sizes[6],
                ),
                Label(label="Wifi is off"),
            ],
        )
        self.stack.add_named(self.enabled_content, "on")
        self.stack.add_named(self.disabled_content, "off")
        self.add(self.stack)

    def connect_signals(self):
        self.connect("button-press-event", self.on_bg_clicked)
        self.network_client.connect("device-ready", self.on_device_ready)

    def on_device_ready(self, *args):
        if self.network_client.wifi_device and self.wifi_device is None:
            self.wifi_device = self.network_client.wifi_device
            self.wifi_device.connect("changed", self.update_list)
            self.wifi_device.scan()
            GLib.timeout_add_seconds(10, self.periodic_scan)
            powered = self.wifi_device.enabled
            self.stack.set_visible_child_name("on" if powered else "off")
            self.show_all()

    def on_tab_selected(self):
        return

    def on_refresh_clicked(self, *_):
        self.start_scan()
        self._expanded_bssid = None
        self._force_full_refresh = True
        if self._manual_scan_timeout_id is not None:
            GLib.source_remove(self._manual_scan_timeout_id)
        self._manual_scan_timeout_id = GLib.timeout_add_seconds(
            12, self.finish_manual_scan_message
        )
        self.show_searching_state()

    def start_scan(self):
        if not self.wifi_device or not self.wifi_device.enabled:
            return
        self.wifi_device.scan()

    def periodic_scan(self):
        if self.wifi_device and self.wifi_device.enabled:
            self.wifi_device.scan()
        return True

    def finish_manual_scan_message(self):
        self._manual_scan_timeout_id = None
        self.update_list()
        return False

    def show_searching_state(self):
        self.count_label.set_label("Searching...")
        for child in self.ap_list.get_children():
            self.ap_list.remove(child)
        self.list_stack.set_visible_child_name("empty")
        self.show_all()

    def update_list(self, *args):
        if self._update_pending:
            return
        self._update_pending = True
        GLib.timeout_add(150, self.do_update)

    def do_update(self):
        self._update_pending = False
        if not self.wifi_device:
            return False

        powered = self.wifi_device.enabled
        self.stack.set_visible_child_name("on" if powered else "off")
        state = self.wifi_device.state
        access_points = [ap for ap in self.wifi_device.access_points if ap["ssid"]]

        if self._manual_scan_timeout_id is not None and access_points:
            self._manual_scan_timeout_id = None

                                                    
        seen_set: set = set()
        count = sum(
            1
            for ap in access_points
            if ap["ssid"] not in seen_set and not seen_set.add(ap["ssid"])
        )
        if self._manual_scan_timeout_id is not None:
            self.count_label.set_label("Searching...")
        else:
            self.count_label.set_label(
                f"{count} Network{'s' if count != 1 else ''} Available"
            )

                                                                                                   
        for c in self.ap_list.get_children():
            if (
                not self._force_full_refresh
                and hasattr(c, "password_revealer")
                and c.password_revealer.get_reveal_child()
            ):
                self._expanded_bssid = c.ap["bssid"]
                return False

                                  
        active_bssid = self.wifi_device.active_bssid
        active_ssid = self.wifi_device.ssid if state == "activated" else None
        for ap in access_points:
            if ap.get("active-ap") and ap["active-ap"] == ap["bssid"]:
                active_bssid = ap["bssid"]
                break
        if (
            state
            in (
                "prepare",
                "config",
                "ip_config",
                "ip_check",
                "secondaries",
                "activated",
            )
            and active_bssid
        ):
            self._connecting_bssid = active_bssid
        elif state == "disconnected":
            self._connecting_bssid = None

                                                                         
        seen_ssids: dict = {}
        for ap in access_points:
            ssid = ap["ssid"]
            is_active = ap["bssid"] == active_bssid or (
                active_ssid and ap["ssid"] == active_ssid
            )
            existing = seen_ssids.get(ssid)
            if existing is None or is_active or ap["strength"] > existing["strength"]:
                seen_ssids[ssid] = ap

        row_data = []
        for ap in seen_ssids.values():
            if ap["bssid"] == active_bssid or (
                active_ssid and ap["ssid"] == active_ssid
            ):
                ap_state = state
            elif ap["bssid"] == self._connecting_bssid and state in (
                "failed",
                "need_auth",
            ):
                ap_state = state
            else:
                ap_state = "unknown"
            row_data.append((ap, ap_state))

        print(
            "[wifi-panel] render",
            {
                "state": state,
                "active_bssid": active_bssid,
                "active_ssid": active_ssid,
                "connecting_bssid": self._connecting_bssid,
                "rows": [
                    (
                        ap["ssid"],
                        ap["bssid"],
                        ap_state,
                        ap["secured"],
                        ap["has-profile"],
                    )
                    for ap, ap_state in row_data
                ],
            },
        )

        for c in self.ap_list.get_children():
            self.ap_list.remove(c)
        for ap, ap_state in row_data:
            self.ap_list.add(
                WifiAPWidget(
                    ap,
                    self.network_client,
                    active_state=ap_state,
                    expanded=ap["bssid"] == self._expanded_bssid,
                    on_toggle=self.on_ap_toggled,
                )
            )
        self.list_stack.set_visible_child_name("list" if row_data else "empty")
        self._force_full_refresh = False

        self.show_all()
        return False

    def on_ap_toggled(self, bssid, expanded):
        self._expanded_bssid = bssid if expanded else None
        if not expanded:
            return
        for child in self.ap_list.get_children():
            if getattr(child, "ap", {}).get("bssid") != bssid and hasattr(
                child, "set_expanded"
            ):
                child.set_expanded(False)

    def toggle_wifi(self):
        if self.wifi_device:
            self.wifi_device.enabled = not self.wifi_device.enabled

    def on_bg_clicked(self, widget, event):
        from widgets.panels.displays import DisplayWidget

        DisplayWidget.close_active_popup()
        return False


class WifiAPWidget(Box):
    def __init__(
        self,
        ap,
        network_client,
        active_state="unknown",
        expanded=False,
        on_toggle=None,
        **kwargs,
    ):
        super().__init__(spacing=0, orientation="v", **kwargs)
        self.network_client = network_client
        self.ap = ap
        self.active_state = active_state
        self.on_toggle = on_toggle
        self.needs_password = ap.get("secured", False) and (
            active_state in ("need_auth", "failed") or not ap.get("has-profile", False)
        )
        self._expanded = False

        icon = Image(
            icon_name=ap["icon-name"], icon_size=config.icon_sizes[4]
        )
        name = Label(
            label=ap["ssid"],
            h_align="start",
            h_expand=True,
            ellipsize="end",
            max_chars_width=20,
        )

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
        main_row.add(icon)
        text_box = Box(orientation="v", spacing=4, h_expand=True)
        header_row = Box(spacing=10, h_expand=True)
        header_row.add(name)
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

        self.action_btn = None
        self.password_entry = None
        self.password_prompt = None
        self.password_revealer = None

        if active_state == "activated":
            action_row = Box(spacing=5, h_expand=True, name="controlcenter-action-row")
            action_row.add(Box(h_expand=True))
            self.action_btn = Button(
                label="Disconnect",
                on_clicked=self.on_disconnect_clicked,
                name="controlcenter-btn",
            )
            action_row.add(self.action_btn)
        elif self.needs_password:
            self.password_entry = Gtk.Entry()
            self.password_entry.set_visibility(False)
            self.password_entry.set_hexpand(True)
            self.password_entry.set_margin_start(5)
            self.password_entry.connect("activate", self.do_connect)
            self.password_entry.connect("changed", self.on_password_changed)
            self.password_prompt = Gtk.Label(label="Password:")
            self.password_prompt.set_halign(Gtk.Align.START)
            self.password_prompt.set_valign(Gtk.Align.CENTER)
            self.password_prompt.set_margin_start(13)
            self.password_prompt.set_name("controlcenter-status-label")
            entry_overlay = Gtk.Overlay()
            entry_overlay.add(self.password_entry)
            entry_overlay.add_overlay(self.password_prompt)
            entry_overlay.set_overlay_pass_through(self.password_prompt, True)
            entry_box = Box(h_expand=True)
            entry_box.add(entry_overlay)
            self.action_btn = Button(
                label="Connect", on_clicked=self.do_connect, name="controlcenter-btn"
            )
            action_row = Box(
                spacing=5,
                h_expand=True,
                children=[entry_box, self.action_btn],
                name="controlcenter-action-row",
            )
        else:
            action_row = Box(spacing=5, h_expand=True)
            action_row.add(Box(h_expand=True))
            self.action_btn = Button(
                label="Connect",
                on_clicked=self.on_connect_clicked,
                name="controlcenter-btn",
            )
            if active_state in (
                "prepare",
                "config",
                "ip_config",
                "ip_check",
                "secondaries",
            ):
                self.action_btn.set_sensitive(False)
            action_row.add(self.action_btn)

        self.password_revealer = Revealer(
            child=action_row, transition_type="slide-down", transition_duration=200
        )
        content.add(self.password_revealer)
        self.set_expanded(expanded, notify=False)

    def get_status_text(self):
        if self.active_state == "activated":
            return "Connected"
        if self.active_state in (
            "prepare",
            "config",
            "ip_config",
            "ip_check",
            "secondaries",
        ):
            return "Connecting..."
        if self.active_state == "need_auth":
            return "Wrong password"
        if self.active_state == "failed":
            return "Failed"
        return None

    def get_detail_text(self):
        details = []
        strength = self.ap.get("strength")
        if strength is not None:
            details.append(f"{strength}% signal")
        frequency = self.ap.get("frequency")
        if frequency:
            details.append(self.format_band(frequency))
        if self.active_state != "activated":
            details.append("Secured" if self.ap.get("secured") else "Open")
        return " • ".join(details)

    def format_band(self, frequency):
        if 2400 <= frequency < 2500:
            return "2.4 GHz"
        if 4900 <= frequency < 5900:
            return "5 GHz"
        if 5900 <= frequency < 7100:
            return "6 GHz"
        return f"{frequency} MHz"

    def set_expanded(self, expanded, notify=True):
        self._expanded = expanded
        if expanded:
            self.password_revealer.reveal()
            if self.password_entry:
                GLib.idle_add(self.password_entry.grab_focus)
        else:
            self.password_revealer.unreveal()
        self.arrow_icon.set_from_icon_name(
            "pan-up-symbolic" if expanded else "pan-down-symbolic",
            config.icon_sizes[0],
        )
        if notify and self.on_toggle:
            self.on_toggle(self.ap["bssid"], expanded)

    def on_password_changed(self, *_):
        if self.password_prompt:
            self.password_prompt.set_visible(not bool(self.password_entry.get_text()))

    def on_row_clicked(self, widget, event):
        if event.window != widget.get_window():
            return False
        self.set_expanded(not self._expanded)
        return False

    def on_connect_clicked(self, *_):
        self.network_client.connect_wifi_bssid(self.ap["bssid"])
        self.set_expanded(False)

    def on_disconnect_clicked(self, *_):
        self.network_client.disconnect_wifi()
        self.set_expanded(False)

    def do_connect(self, *_):
        password = self.password_entry.get_text() if self.password_entry else None
        self.network_client.connect_wifi_bssid(
            self.ap["bssid"], password=password if password else None
        )
        if self.password_entry:
            self.password_entry.set_text("")
            self.on_password_changed()
        self.set_expanded(False)
