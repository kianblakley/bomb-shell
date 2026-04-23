                  

import gi
import json
import math
import os
import time

gi.require_version("Gtk", "3.0")
from gi.repository import GLib
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.stack import Stack
from services.bootstrap import niri_service, notifications_service
from utils.config import config
from widgets.common.notification_widget import NotificationWidget

SCREEN_SIZE = niri_service.get_screen_size()


class NotificationHistory(Box):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="v",
            v_align="fill",
            h_align="fill",
            spacing=math.ceil(SCREEN_SIZE[1] / 108),
            name="controlcenter-panel-container",
            **kwargs,
        )
        self.notification_widgets_by_id = {}
        self.notification_history = []
        self.build_ui()
        self.connect_signals()
        self.load_history()
        self.refresh_ui()

    def build_ui(self):
        self.count_label = Label(
            label=self.get_count_text(),
            h_align="start",
            name="controlcenter-section-title",
        )
        self.clear_btn = Button(
            child=Box(
                children=[
                    Image(
                        icon_name="view-list-bullet-symbolic",
                        icon_size=config.icon_sizes[2],
                    ),
                    Label(label="Clear"),
                ],
                spacing=5,
            ),
            on_clicked=lambda *_: self.clear_all(),
            name="controlcenter-btn",
        )
        self.header = Box(
            children=[self.count_label, Box(h_expand=True), self.clear_btn],
            h_expand=True,
            name="controlcenter-panel-header",
        )
        self.history_list = Box(orientation="v", h_expand=True, name="controlcenter-history-list")
        self.scroll = ScrolledWindow(
            child=self.history_list,
            h_expand=True,
            v_expand=True,
            h_scrollbar_policy="never",
            v_scrollbar_policy="automatic",
            overlay_scroll=True,
            name="controlcenter-scrollable",
        )

        self.empty_placeholder = Box(
            orientation="v",
            v_align="center",
            h_align="center",
            spacing=10,
            v_expand=True,
            children=[
                Image(
                    icon_name="notifications", icon_size=config.icon_sizes[6]
                ),
                Label(label="No notifications yet", name="controlcenter-empty-label"),
            ],
        )
        self.stack = Stack(
            transition_type="crossfade", transition_duration=300, v_expand=True
        )
        self.stack.add_named(self.scroll, "history")
        self.stack.add_named(self.empty_placeholder, "empty")

        self.add(self.header)
        self.add(self.stack)

    def connect_signals(self):
        self.connect("button-press-event", self.on_bg_clicked)
        notifications_service.connect("notification_added", self.on_notification_added)

    def get_count_text(self):
        count = len(self.notification_history)
        return f"{count} Notification{'s' if count != 1 else ''}"

    def update_count(self):
        self.count_label.set_label(self.get_count_text())
        self.stack.set_visible_child_name(
            "history" if len(self.notification_history) > 0 else "empty"
        )

    def on_notification_added(self, _, id):
        notification = notifications_service.get_notification_from_id(id)
        notification_data = {
            "id": notification.id,
            "summary": notification.summary,
            "body": notification.body,
            "app_name": notification.app_name,
            "app_icon": notification.app_icon,
            "image_file": notification.image_file,
            "actions": [
                {"label": a.label, "identifier": a.identifier}
                for a in notification.actions
            ],
            "time": time.time(),
        }
        self.notification_history.insert(0, notification_data)
        self.save_history()
        self.add_notification_to_list(notification_data, at_top=True)
        self.update_count()

    def remove_notification(self, notification_id):
        self.notification_history = [
            notification
            for notification in self.notification_history
            if notification.get("id") != notification_id
        ]
        self.save_history()
        if notification_id in self.notification_widgets_by_id:
            widget = self.notification_widgets_by_id.pop(notification_id)
            widget.unreveal_all(
                callback=lambda: (self.history_list.remove(widget), self.update_count())
            )

    def clear_all(self):
        self.notification_history = []
        self.save_history()
        for widget in self.notification_widgets_by_id.values():
            widget.unreveal_all(callback=lambda w=widget: self.history_list.remove(w))
        self.notification_widgets_by_id.clear()
        GLib.timeout_add(600, self.update_count)

    def load_history(self):
        history_path = config.notifications_path
        if os.path.exists(history_path):
            with open(history_path, "r") as f:
                try:
                    self.notification_history = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    self.notification_history = []

    def save_history(self):
        history_path = config.notifications_path
        with open(history_path, "w") as f:
            json.dump(self.notification_history, f)

    def refresh_ui(self):
        for d in self.notification_history[::-1]:
            self.add_notification_to_list(d, at_top=True)
        self.history_list.show_all()
        self.update_count()

    def add_notification_to_list(self, d, at_top=True):
        nid = d.get("id")
        widget = NotificationWidget(
            d,
            is_history=True,
            on_close=lambda: self.remove_notification(nid),
            max_chars_width=NotificationWidget.__init__.__defaults__[2] + 3,
        )
        if at_top:
            self.history_list.pack_start(widget, False, False, 0)
            self.history_list.reorder_child(widget, 0)
        else:
            self.history_list.add(widget)

        self.notification_widgets_by_id[nid] = widget
        widget.show_all()
        widget.reveal_all()

    def on_bg_clicked(self, widget, event):
        return False
