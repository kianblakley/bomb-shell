from services.bootstrap import app_state, niri_service, notifications_service
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from fabric import Application
from fabric.widgets.revealer import Revealer
from widgets.common.notification_widget import NotificationWidget
from utils.config import config

SCREEN_SIZE = niri_service.get_screen_size()


class NotificationsOSD(WaylandWindow):
    def __init__(self, **kwargs):
        super().__init__(layer="overlay", anchor="top right", **kwargs)
        self.notifications = notifications_service
        self.build_ui()
        self.connect_signals()

    def build_ui(self):
        osd_width = SCREEN_SIZE[0] // 5
        self.notifications_container = Box(
            orientation="v", name="notifications-container", size=(osd_width, 18)
        )
        self.notifications_frame = Box()
        self.root_box = Box(orientation="v")

        # if config.get_setting("rounded_corners"):
        #     self.left_corner = Corner(
        #         orientation="top-right",
        #         size=(config.corner_size, config.corner_size),
        #         name="notifications-corner",
        #         v_align="start",
        #     )
        #     self.bottom_corner = Corner(
        #         orientation="top-right",
        #         size=(config.corner_size, config.corner_size),
        #         name="notifications-corner",
        #         v_align="end",
        #         h_align="end",
        #     )
        #     self.notifications_frame.add(self.left_corner)
        #     self.notifications_frame.add(self.notifications_container)
        #     self.root_box.add(self.notifications_frame)
        #     self.root_box.add(self.bottom_corner)
        # else:
        self.notifications_frame.add(self.notifications_container)
        self.root_box.add(self.notifications_frame)

        self.revealer = Revealer(
            child=self.root_box, transition_type="slide-down", transition_duration=300
        )
        self.revealer_container = Box(
            size=1, children=[self.revealer], name="notifications-revealer"
        )
        self.children = self.revealer_container

    def connect_signals(self):
        self.notifications.connect("notification_added", self.on_notification_added)

    def on_notification_added(self, _, id):
        if app_state.dnd:
            return

        notification = self.notifications.get_notification_from_id(id)
        new_notification = NotificationWidget(notification)

                                                                    
        self.notifications_container.pack_end(new_notification, False, False, 0)

        self.revealer.reveal()
        new_notification.reveal_all()

        notification.connect(
            "closed",
            lambda: new_notification.unreveal_all(
                callback=lambda: (
                    self.notifications_container.remove(new_notification),
                    self.revealer.unreveal()
                    if len(self.notifications_container.get_children()) == 0
                    else None,
                )
            ),
        )


if __name__ == "__main__":
    notifications_window = NotificationsOSD()
    app = Application("notif", notifications_window, open_inspector=False)
    app.set_stylesheet_from_file(config.style_sheet.with_name("notifications.css"))
    app.run()
