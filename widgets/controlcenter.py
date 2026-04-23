
import gi
import math
import subprocess
from datetime import datetime

from services.bootstrap import niri_service
from fabric import Application, Fabricator
from fabric.widgets.label import Label
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from fabric.widgets.revealer import Revealer
from services.bootstrap import (
    app_state,
    bluetooth_service,
    network_service,
    upower_service,
)
from utils.config import config
from fabric.widgets.image import Image
from fabric.widgets.button import Button
from fabric.widgets.svg import Svg
from fabric.widgets.stack import Stack
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.eventbox import EventBox
from widgets.panels.notification_history import NotificationHistory
from widgets.panels.audio import AudioPanel
from widgets.panels.bluetooth import BluetoothPanel
from widgets.panels.wifi import WifiPanel
from widgets.panels.displays import DisplaysPanel

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib

SCREEN_SIZE = niri_service.get_screen_size()
BATTERY = "/org/freedesktop/UPower/devices/battery_BAT0"

ICON_SIZE = config.icon_sizes[3]
CC_WIDTH = int(SCREEN_SIZE[0] / 4.5)


class ControlCenter(WaylandWindow):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay",
            anchor="top, bottom, right",
            keyboard_mode="on-demand",
            size=(CC_WIDTH, -1),
            **kwargs,
        )
        self.build_ui()
        self.connect_signals()

    def build_ui(self):
        self.profile_picture = ProfilePicture()
        self.status = Status()
        self.power_button = PowerButton()
        self.device_panels = Devices(parent_window=self)
        self.quick_access_buttons = QuickAccessButtons(self.device_panels)
        self.calendar = Calendar()

        self.main_container = Box(
            orientation="v",
            size=(CC_WIDTH, SCREEN_SIZE[1]),
            children=[
                Box(
                    children=[self.profile_picture, self.status, self.power_button],
                    name="controlcenter-top-row",
                    spacing=12,
                ),
                self.quick_access_buttons,
                self.device_panels,
                self.calendar,
            ],
            h_align="center",
            v_align="center",
            name="controlcenter-main",
            spacing=10,                          
        )

        self.bg_event_box = EventBox(child=self.main_container)

        # self.corners = Box(orientation="v")
        # if config.get_setting("rounded_corners"):
        #     self.corners.add(
        #         Corner(
        #             orientation="top-right",
        #             size=config.corner_size,
        #             v_align="start",
        #             h_align="end",
        #             name="controlcenter-corner",
        #         )
        #     )
        #     self.corners.add(Box(v_expand=True))
        #     self.corners.add(
        #         Corner(
        #             orientation="bottom-right",
        #             size=config.corner_size,
        #             v_align="end",
        #             h_align="end",
        #             name="controlcenter-corner",
        #         )
        #     )
        # else:
        #     self.corners.add(Box(v_expand=True))

        self.revealer = Revealer(
            child=Box(children=[self.bg_event_box]),
            transition_duration=200,
            transition_type="slide-left",
        )
        self.revealer_container = Box(
            children=[self.revealer], size=1, name="controlcenter-revealer-container"
        )
        self.add(self.revealer_container)

    def connect_signals(self):
        self.bg_event_box.connect("button-press-event", self.on_bg_clicked)

    def on_bg_clicked(self, widget, event):
        self.power_button.reset()
        return False

    def toggle(self):
        if self.revealer.child_revealed:
            self.revealer.unreveal()
            self.power_button.reset()
            from widgets.common.popupmenu import PopupMenu

            PopupMenu.clear_all()
        else:
            self.revealer.reveal()


class ProfilePicture(Box):
    def __init__(self, **kwargs):
        super().__init__(name="controlcenter-profile-picture", **kwargs)
        size = math.ceil(SCREEN_SIZE[1] / 20)
        try:
            profile_picture = config.get_setting("profile_picture")
            if str(profile_picture).endswith(".svg"):
                self.image = Svg(svg_file=str(profile_picture), size=size)
            else:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(profile_picture), size, size, True
                )
                self.image = Image(pixbuf=pixbuf)
        except Exception:
            self.image = Image(icon_name="avatar-default", size=size)
        self.add(self.image)


class Status(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="controlcenter-status",
            spacing=12,
        )
        self.time = Label(h_align="start")
        self.time_fabricator = Fabricator(
            interval=1000,
            poll_from=lambda _: datetime.now().strftime("%I:%M %p: %a %d %b"),
            on_changed=lambda _, time: self.time.set_label(time),
        )
        self.upower = upower_service
        self.battery_percentage = Label(name="controlcenter-status-label")
        self.battery_state = Label(name="controlcenter-status-label")
        try:
            self.battery_fabricator = Fabricator(
                interval=1000,
                poll_from=lambda _: self.upower.get_full_device_information(BATTERY),
                on_changed=self.update_battery_info,
            )
        except Exception:
            self.battery_percentage.set_label("No battery")

        self.battery = Box(children=[self.battery_percentage, self.battery_state])
        self.add(
            Box(
                orientation="v",
                v_align="center",
                children=[self.time, self.battery],
                spacing=0,
            )
        )

    def update_battery_info(self, _, info):
        if not info:
            self.battery_percentage.set_label("No battery")
            self.battery_state.set_label("")
            return

        percent = int(info.get("Percentage", 0))
        state = int(info.get("State", 0))
        time_to_empty = int(info.get("TimeToEmpty", 0))

        self.battery_percentage.set_label(f"{percent}%")

        state_text = ""
        if state == 1:            
            state_text = " (Charging)"
        elif state == 2:               
            if time_to_empty > 0:
                h, m = divmod(time_to_empty // 60, 60)
                state_text = f" ({h}h {m}m remaining)"
            else:
                state_text = " (Discharging)"
        elif state == 3:
            state_text = " (Empty)"
        elif state == 4:
            state_text = " (Fully charged)"
        elif state == 5:
            state_text = " (Pending charge)"
        elif state == 6:
            state_text = " (Pending discharge)"
        else:
            state_text = ""

        if state_text:
            self.battery_state.set_label(state_text)
        else:
            self.battery_state.set_label("")


class PowerButton(Box):
    def __init__(self, **kwargs):
        super().__init__(h_expand=True, h_align="end", v_align="center", **kwargs)
        self.pending_command = None

        self.sleep_button = Button(
            child=Image(icon_name="system-suspend-symbolic", icon_size=ICON_SIZE),
            on_clicked=lambda *_: self.prepare_confirm("Sleep", "systemctl suspend"),
            name="controlcenter-power-btn",
        )
        self.reboot_button = Button(
            child=Image(icon_name="system-reboot-symbolic", icon_size=ICON_SIZE),
            on_clicked=lambda *_: self.prepare_confirm("Reboot", "systemctl reboot"),
            name="controlcenter-power-btn",
        )
        self.logout_button = Button(
            child=Image(icon_name="system-log-out-symbolic", icon_size=ICON_SIZE),
            on_clicked=lambda *_: self.prepare_confirm(
                "Logout", "niri msg action quit"
            ),
            name="controlcenter-power-btn",
        )
        self.shutdown_button = Button(
            child=Image(icon_name="system-shutdown-symbolic", icon_size=ICON_SIZE),
            on_clicked=self.on_main_clicked,
            name="controlcenter-power-btn-main",
        )

        self.extra_buttons = Box(
            children=[self.sleep_button, self.reboot_button, self.logout_button],
            spacing=0,
        )
        self.revealer = Revealer(
            child=self.extra_buttons,
            transition_type="slide-left",
            transition_duration=300,
        )

                                 
        self.buttons_box = Box(
            children=[self.revealer, self.shutdown_button],
            spacing=0,
            h_align="end",
            name="controlcenter-power-bar",
        )

        self.confirmation_label = Label(
            name="controlcenter-power-confirm-label", h_expand=True, h_align="center"
        )
        self.confirmation_button = Button(
            child=self.confirmation_label,
            on_clicked=self.execute_action,
            name="controlcenter-power-bar",
            h_expand=True,
        )

        self.stack = Stack(
            transition_type="crossfade",
            transition_duration=300,
            h_align="end",
            h_expand=True,
        )
        self.stack.add_named(self.buttons_box, "buttons")
        self.stack.add_named(self.confirmation_button, "confirm")

        self.fixed_size_box = Box(children=[self.stack], h_align="end", h_expand=True)
        self.add(self.fixed_size_box)

    def reset(self):
        if self.stack.get_visible_child_name() == "confirm":
            self.stack.set_visible_child_name("buttons")
            self.revealer.unreveal()
            GLib.timeout_add(300, self.finish_reset)
        else:
            self.revealer.unreveal()
            self.finish_reset()
        self.pending_command = None

    def finish_reset(self):
        self.fixed_size_box.set_size_request(-1, -1)
        return False

    def on_main_clicked(self, *args):
        if not self.revealer.child_revealed:
            self.revealer.reveal()
        else:
            self.prepare_confirm("Power Off", "systemctl poweroff")

    def prepare_confirm(self, label, command):
        self.fixed_size_box.set_size_request(self.stack.get_allocated_width(), -1)
        self.confirmation_label.set_label(f"{label}?")
        self.pending_command = command
        self.stack.set_visible_child_name("confirm")

    def execute_action(self, *args):
        if self.pending_command:
            subprocess.run(self.pending_command.split())
        self.reset()


class QuickAccessButtons(Box):
    def __init__(self, device_panels, **kwargs):
        super().__init__(
            name="controlcenter-quickaccess-container", spacing=5, **kwargs
        )
        self.device_panels = device_panels
        self.dnd_btn = Button(
            child=Image(icon_name="notifications", icon_size=ICON_SIZE),
            on_clicked=self.on_dnd_clicked,
            name="controlcenter-quickaccess-btn",
        )
        self.wifi_btn = Button(
            child=Image(icon_name="network-wireless", icon_size=ICON_SIZE),
            on_clicked=self.on_wifi_clicked,
            name="controlcenter-quickaccess-btn",
        )
        self.bluetooth_btn = Button(
            child=Image(icon_name="bluetooth-active", icon_size=ICON_SIZE),
            on_clicked=self.on_bluetooth_clicked,
            name="controlcenter-quickaccess-btn",
        )
        self.add(self.dnd_btn)
        self.add(self.wifi_btn)
        self.add(self.bluetooth_btn)
        bluetooth_service.connect("changed", lambda *_: self.update_icons())
        network_service.connect("device-ready", self.on_network_ready)
        self.update_icons()

    def on_network_ready(self, *args):
        if network_service.wifi_device:
            network_service.wifi_device.connect(
                "changed", lambda *_: self.update_icons()
            )
        self.update_icons()

    def update_icons(self):
        bt_on = self.device_panels.bluetooth.bluetooth_client.powered
        self.bluetooth_btn.get_child().set_from_icon_name(
            "bluetooth-active" if bt_on else "bluetooth-disabled", ICON_SIZE
        )
        if not bt_on:
            self.bluetooth_btn.add_style_class("off")
        else:
            self.bluetooth_btn.remove_style_class("off")

        wifi_on = (
            self.device_panels.wifi.wifi_device.enabled
            if self.device_panels.wifi.wifi_device
            else False
        )
        self.wifi_btn.get_child().set_from_icon_name(
            "network-wireless" if wifi_on else "network-wireless-offline", ICON_SIZE
        )
        if not wifi_on:
            self.wifi_btn.add_style_class("off")
        else:
            self.wifi_btn.remove_style_class("off")

    def on_dnd_clicked(self):
        app_state.dnd = not app_state.dnd
        self.dnd_btn.get_child().set_from_icon_name(
            "notifications-disabled" if app_state.dnd else "notifications", ICON_SIZE
        )
        if app_state.dnd:
            self.dnd_btn.add_style_class("off")
        else:
            self.dnd_btn.remove_style_class("off")

    def on_bluetooth_clicked(self):
        self.device_panels.bluetooth.toggle_power()
        GLib.timeout_add(100, self.update_icons)

    def on_wifi_clicked(self):
        self.device_panels.wifi.toggle_wifi()
        GLib.timeout_add(100, self.update_icons)


class CustomNavbar(Box):
    def __init__(self, stack, **kwargs):
        super().__init__(
            orientation="h",
            name="controlcenter-navbar",
            spacing=0,
            h_align="start",
            **kwargs,
        )
        self.stack = stack
        self.buttons = {}
        tabs = [
            ("notification_history", "History", "notifications-symbolic"),
            ("wifi", "Wifi", "network-wireless-symbolic"),
            ("bluetooth", "Bluetooth", "bluetooth-active-symbolic"),
            ("audio", "Audio", "audio-speakers-symbolic"),
            ("displays", "Displays", "video-display-symbolic"),
        ]
        for name, title, icon_name in tabs:
            btn = Button(name="controlcenter-navbar-btn")
            content = Box(spacing=5)
            icon = Image(icon_name=icon_name, icon_size=ICON_SIZE)
            label = Label(label=title, name="controlcenter-navbar-label")
            revealer = Revealer(
                child=label, transition_type="slide-right", transition_duration=300
            )
            content.add(icon)
            content.add(revealer)
            btn.add(content)
            btn.connect("clicked", lambda b, n=name: self.on_tab_clicked(n))
            self.add(btn)
            self.buttons[name] = {"button": btn, "revealer": revealer}
        self.stack.connect("notify::visible-child-name", self.update_tabs)
        self.update_tabs()

    def on_tab_clicked(self, name):
        self.stack.set_visible_child_name(name)
        from widgets.common.popupmenu import PopupMenu

        PopupMenu.clear_all()

    def update_tabs(self, *args):
        active_name = self.stack.get_visible_child_name()
        for name, widgets in self.buttons.items():
            is_active = name == active_name
            widgets["revealer"].set_reveal_child(is_active)
            if is_active:
                widgets["button"].add_style_class("active")
            else:
                widgets["button"].remove_style_class("active")


class Devices(Box):
    def __init__(self, parent_window, **kwargs):
        super().__init__(
            orientation="v", v_expand=True, name="controlcenter-devices-container"
        )
        self.notification_history = NotificationHistory()
        self.audio = AudioPanel(parent_window=parent_window)
        self.bluetooth = BluetoothPanel()
        self.wifi = WifiPanel()
        self.displays = DisplaysPanel(parent_window=parent_window)
        self.stack = Stack(
            transition_type="slide-left-right",
            transition_duration=200,
            name="controlcenter-devices-stack",
            v_expand=True,
        )
        self.stack.add_named(self.notification_history, "notification_history")
        self.stack.add_named(self.wifi, "wifi")
        self.stack.add_named(self.bluetooth, "bluetooth")
        self.stack.add_named(self.audio, "audio")
        self.stack.add_named(self.displays, "displays")
        self.stack.connect("notify::visible-child-name", self.on_visible_panel_changed)
        self.navbar = CustomNavbar(self.stack)
        self.navbar_scrolled = ScrolledWindow(
            child=self.navbar,
            h_scrollbar_policy="external",
            v_scrollbar_policy="never",
            h_expand=True,
        )
        self.add(self.navbar_scrolled)
        self.add(self.stack)

    def on_visible_panel_changed(self, *args):
        panel_name = self.stack.get_visible_child_name()
        if panel_name == "wifi":
            self.wifi.on_tab_selected()
        elif panel_name == "bluetooth":
            self.bluetooth.on_tab_selected()


class Calendar(Box):
    def __init__(self, **kwargs):
        super().__init__(name="controlcenter-calendar-box")
        self.calendar = Gtk.Calendar(name="controlcenter-calendar")
        self.calendar.set_visible(True)
        self.calendar.set_hexpand(True)
        self.add(self.calendar)
        self.calendar.mark_day(datetime.now().day)
        self.calendar.select_day(datetime.now().day)


if __name__ == "__main__":
    controlcenter = ControlCenter()
    app = Application("controlcenter", controlcenter, open_inspector=False)
    app.set_stylesheet_from_file(config.style_sheet.with_name("controlcenter.css"))
    app.run()
