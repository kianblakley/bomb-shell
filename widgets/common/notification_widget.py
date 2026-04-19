from services.bootstrap import niri_service
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from fabric.widgets.image import Image
from fabric.widgets.button import Button
from fabric.widgets.eventbox import EventBox
from fabric.utils import invoke_repeater
from utils.config import config
import time
from gi.repository import GLib, GdkPixbuf, Gdk, Gtk
import urllib.parse
import math

IMAGE_SIZE = (36, 36)
DEFAULT_TIMEOUT = 10
ACTION_BUTTONS_PER_ROW = 2
SCREEN_SIZE = niri_service.get_screen_size()

NOTIFICATION_FALLBACK_ICON_CANDIDATES = [
                      
                               
                          
                                                  
                                
                                    
                         
    "org.xfce.notification",
    "xfce4-notifyd",
    "bell",
    "stock_bell",
    "preferences-desktop-notification-bell",
    "preferences-system-notifications-symbolic",
    "notifications-symbolic",
    "dialog-information-symbolic",
    "mail-unread-symbolic",
    "appointment-soon-symbolic",
    "emblem-important-symbolic",
    "preferences-system-notifications",
    "notifications",
    "dialog-information",
    "mail-unread",
    "appointment-soon",
    "emblem-important",
]


def resolve_notification_fallback_icon(candidates=None):
    icon_names = candidates or NOTIFICATION_FALLBACK_ICON_CANDIDATES
    theme = Gtk.IconTheme.get_default()
    if theme is None:
        return icon_names[0] if icon_names else "image-missing"
    for icon_name in icon_names:
        if theme.lookup_icon(icon_name, 30, Gtk.IconLookupFlags.FORCE_SIZE):
            return icon_name
    return icon_names[0] if icon_names else "image-missing"


class NotificationWidget(Box):
    def __init__(
        self,
        notification,
        is_history=False,
        on_close=None,
        max_chars_width=math.floor(SCREEN_SIZE[0] / 50),
        fallback_icon_names=None,
        **kwargs,
    ):
        super().__init__(h_expand=True, h_align="fill", **kwargs)
        self.max_chars_width = max_chars_width
        self.notification_data = notification
        self.is_history = is_history
        self.on_close = on_close
        self.fallback_icon_name = resolve_notification_fallback_icon(
            fallback_icon_names
        )

                               
        if isinstance(notification, dict):
            self.summary = notification.get("summary", "")
            self.body = notification.get("body", "")
            self.app_name = notification.get("app_name", "")
            self.app_icon = notification.get("app_icon", "")
            self.image_file = notification.get("image_file", None)
            self.image_pixbuf = None
            self.timeout = -1
            self.actions = notification.get("actions", [])
            self.id = notification.get("id", 0)
            self.is_dict = True
        else:
            self.summary = notification.summary
            self.body = notification.body
            self.app_name = notification.app_name
            self.app_icon = notification.app_icon
            self.image_file = notification.image_file
            self.image_pixbuf = notification.image_pixbuf
            self.timeout = notification.timeout
            self.actions = notification.actions
            self.id = notification.id
            self.is_dict = False

                          
        self.slide_left_revealer = Revealer(
            transition_duration=300, transition_type="slide-left", h_align="end"
        )
        self.slide_down_revealer = Revealer(
            transition_duration=300,
            transition_type="slide-down",
            child=self.slide_left_revealer,
            h_expand=True,
        )
        self.add(self.slide_down_revealer)

                       
        self.summary_label = None
        self.truncated_section_revealer = None
        self.setup_ui_elements()

                                               
        invoke_repeater(10, self.initialize_content, initial_call=False)

    def setup_ui_elements(self):
        prefix = "notifications"
        self.content_box = Box(
            orientation="v",
            spacing=5,
            h_expand=True,
            name=f"{prefix}-widget"
            if not self.is_history
            else f"{prefix}-history-widget",
        )

        self.image_content = Box(v_align="start")
        self.text_content = Box(
            orientation="v", h_expand=True, h_align="fill", name=f"{prefix}-text-box"
        )
        self.expanded_title_content = Box()
        self.expanded_title_content_revealer = Revealer(
            child=self.expanded_title_content,
            transition_type="slide-down",
            transition_duration=300,
        )

        self.line_one_box = Box()
        self.expanded_text_content = Box()
        self.expanded_text_content_revealer = Revealer(
            child=self.expanded_text_content,
            transition_type="slide-down",
            transition_duration=300,
        )

        self.open_close_buttons = Box(orientation="v", v_align="start", spacing=2)

        self.main_content = Box(
            orientation="h",
            children=[self.image_content, self.text_content, self.open_close_buttons],
            spacing=10,
            h_expand=True,
        )

        self.action_buttons = Box(orientation="v", h_expand=True)
        self.action_buttons_revealer = Revealer(
            child=self.action_buttons,
            transition_type="slide-down",
            transition_duration=300,
            h_expand=True,
        )

        self.content_box.children = [self.main_content, self.action_buttons_revealer]

                         
        self.event_box = EventBox(
            child=self.content_box,
            events=["enter-notify", "leave-notify", "button-release"],
            name="notifications-event-box",
            h_expand=True,
        )

                           
        self.event_box.connect("button-release-event", lambda *_: self.toggle_expand())
        self.event_box.connect(
            "enter-notify-event",
            lambda *_: (
                self.content_box.add_style_class("hovered"),
                self.pause_timer(),
            ),
        )
        self.event_box.connect(
            "leave-notify-event",
            lambda _, event: (
                None
                if event.detail == Gdk.NotifyType.INFERIOR
                else (
                    self.content_box.remove_style_class("hovered"),
                    self.unpause_timer(),
                )
            ),
        )

                     
        self.timer_paused = False
        self.expanded = False

                             
        try:
            if self.image_pixbuf:
                scaled = self.image_pixbuf.scale_simple(
                    IMAGE_SIZE[0], IMAGE_SIZE[1], GdkPixbuf.InterpType.BILINEAR
                )
                self.image_content.add(Image(pixbuf=scaled))
            elif self.image_file:
                path = self.parse_file_path(self.image_file)
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
                scaled = pixbuf.scale_simple(
                    IMAGE_SIZE[0], IMAGE_SIZE[1], GdkPixbuf.InterpType.BILINEAR
                )
                self.image_content.add(Image(pixbuf=scaled))
            elif self.app_icon:
                path = self.parse_file_path(self.app_icon)
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
                scaled = pixbuf.scale_simple(
                    IMAGE_SIZE[0], IMAGE_SIZE[1], GdkPixbuf.InterpType.BILINEAR
                )
                self.image_content.add(Image(pixbuf=scaled))
            else:
                self.image_content.add(
                    Box(
                        children=Image(
                            icon_name=self.fallback_icon_name,
                            icon_size=config.icon_sizes[5],
                        ),
                        name=f"{prefix}-svg",
                    )
                )
        except Exception:
            self.image_content.add(
                Box(
                    children=Image(
                        icon_name=self.fallback_icon_name,
                        icon_size=config.icon_sizes[5],
                    ),
                    name=f"{prefix}-svg",
                )
            )

        if self.app_name:
            self.expanded_title_content.add(
                Label(
                    label=f"{self.app_name}", name=f"{prefix}-app-name", h_align="start"
                )
            )

        self.time_created = time.time()
        self.time_since_created = Label(name=f"{prefix}-app-name", h_align="start")
        self.time_since_created_bold = Label(name=f"{prefix}-time")
        self.time_since_created_bold_revealer = Revealer(
            child=self.time_since_created_bold,
            transition_type="crossfade",
            transition_duration=300,
            child_revealed=True,
        )
        invoke_repeater(1000, self.update_time)

        self.expanded_title_content.add(self.time_since_created)
        self.text_content.add(self.expanded_title_content_revealer)

        if self.summary:
            self.summary_container = Box(h_expand=True, h_align="fill")
            self.summary_label = Label(
                name=f"{prefix}-summary",
                label=self.summary[: self.max_chars_width - 18].rstrip(" "),
            )
            self.summary_container.add(self.summary_label)
            self.summary_container.add(self.time_since_created_bold_revealer)
            self.text_content.add(self.summary_container)
            self.text_content.add(self.line_one_box)

        if self.body:
            if len(self.body) <= self.max_chars_width:
                self.line_one_box.add(
                    Label(label=self.body, name=f"{prefix}-body", h_align="start")
                )
            else:
                line_one, line_two = (
                    self.body[: self.max_chars_width],
                    self.body[self.max_chars_width :],
                )
                for i, char in enumerate(self.body[self.max_chars_width :: -1]):
                    if char == " ":
                        line_one = self.body[: self.max_chars_width - i].rstrip()
                        line_two = self.body[self.max_chars_width - i :].lstrip()
                        truncated_section = (
                            self.body[
                                self.max_chars_width - i : self.max_chars_width - 3
                            ]
                            + "..."
                        )
                        break
                self.line_one_box.add(
                    Label(label=line_one, name=f"{prefix}-body", h_align="start")
                )
                self.truncated_section_revealer = Revealer(
                    child=Label(label=truncated_section, name=f"{prefix}-body"),
                    transition_type="crossfade",
                    transition_duration=100,
                    child_revealed=True,
                )
                self.line_one_box.add(self.truncated_section_revealer)
                self.expanded_text_content.add(
                    Label(
                        label=line_two,
                        name=f"{prefix}-body",
                        h_align="start",
                        line_wrap="word",
                        max_chars_width=self.max_chars_width,
                    )
                )
                self.text_content.add(self.expanded_text_content_revealer)

                      
        if not self.is_history:
            close_button = Button(
                child=Image(
                    icon_name="window-close-symbolic",
                    icon_size=config.icon_sizes[1],
                ),
                name=f"{prefix}-close",
            )
            self.remaining_timeout = float(
                self.timeout if self.timeout != -1 else DEFAULT_TIMEOUT
            )
            invoke_repeater(10, self.decrement_timer, self.notification_data)
        else:
            close_button = Button(
                child=Image(
                    icon_name="window-close-symbolic",
                    icon_size=config.icon_sizes[1],
                ),
                name=f"{prefix}-close",
            )

        def on_close_clicked(*args):
            if self.is_history and self.on_close:
                self.on_close()
            elif not self.is_history:
                self.notification_data.close()
            return True

        close_button.connect("button-release-event", on_close_clicked)
        self.open_close_buttons.add(close_button)
        self.expanded_icon = Box(
            children=Image(
                icon_name="pan-down-symbolic", icon_size=config.icon_sizes[2]
            ),
            name=f"{prefix}-expand",
        )
        self.open_close_buttons.add(self.expanded_icon)

                 
        if self.actions:
            action_row = []
            for action in self.actions:
                label = (
                    action.get("label", "View")
                    if self.is_dict
                    else (action.label or "View")
                )
                on_click = (
                    (lambda *_: (self.on_close(), True)[1])
                    if self.is_dict
                    else (lambda *_, a=action: (a.invoke(), True)[1])
                )
                btn = Button(
                    label=label,
                    on_clicked=on_click,
                    name=f"{prefix}-action-button",
                    h_expand=True,
                )
                btn.connect(
                    "enter_notify_event", lambda b, *_: b.add_style_class("hovered")
                )
                btn.connect(
                    "leave_notify_event", lambda b, *_: b.remove_style_class("hovered")
                )
                action_row.append(btn)
                if len(action_row) == ACTION_BUTTONS_PER_ROW:
                    self.action_buttons.add(
                        Box(children=action_row, spacing=10, h_expand=True)
                        .build()
                        .set_homogeneous(True)
                        .unwrap()
                    )
                    action_row = []
            if action_row:
                self.action_buttons.add(
                    Box(children=action_row, spacing=10, h_expand=True)
                    .build()
                    .set_homogeneous(True)
                    .unwrap()
                )

    def initialize_content(self):
        width = self.get_allocated_width()
                                                   
        if width <= 1:
            return True               

                                                             
        self.event_box.set_size_request(width, -1)
        self.slide_left_revealer.add(self.event_box)

    def reveal_all(self):
        self.slide_down_revealer.reveal()
        GLib.timeout_add(
            self.slide_down_revealer.transition_duration,
            self.slide_left_revealer.reveal,
        )

    def unreveal_all(self, callback=None):
        self.slide_left_revealer.unreveal()
        GLib.timeout_add(
            self.slide_left_revealer.transition_duration,
            self.slide_down_revealer.unreveal,
        )
        if callback:
            total_duration = (
                self.slide_left_revealer.transition_duration
                + self.slide_down_revealer.transition_duration
            )
            GLib.timeout_add(total_duration, callback)

    def decrement_timer(self, notification):
        if not self.timer_paused:
            self.remaining_timeout -= 0.01
        if self.remaining_timeout <= 0:
            if hasattr(notification, "close"):
                notification.close()
            return False
        return True

    def pause_timer(self):
        self.timer_paused = True

    def unpause_timer(self):
        self.timer_paused = False

    def parse_file_path(self, path):
        return (
            urllib.parse.unquote(urllib.parse.urlparse(path).path)
            if path.startswith("file://")
            else path
        )

    def toggle_expand(self):
        self.expanded = not self.expanded
        icon = "pan-up-symbolic" if self.expanded else "pan-down-symbolic"
        self.expanded_icon.children[0].set_from_icon_name(
            icon, config.icon_sizes[2]
        )
        self.action_buttons_revealer.set_reveal_child(self.expanded)
        self.expanded_text_content_revealer.set_reveal_child(self.expanded)
        self.expanded_title_content_revealer.set_reveal_child(self.expanded)
        self.time_since_created_bold_revealer.set_reveal_child(not self.expanded)
        if self.truncated_section_revealer:
            self.truncated_section_revealer.set_reveal_child(not self.expanded)

    def update_time(self):
        diff = int(time.time() - self.time_created)
        if diff < 60:
            label = "now"
        elif diff < 3600:
            label = f"{diff // 60} min"
        elif diff < 86400:
            label = f"{diff // 3600} hr"
        else:
            label = f"{diff // 86400} day"
        if label != "now" and int(label.split(" ")[0]) != 1:
            label += "s"
        self.time_since_created.set_label(f" • {label}")
        self.time_since_created_bold.set_label(f" • {label}")
        return True
