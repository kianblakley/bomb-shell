from fabric import Application
from utils.config import config
from widgets.appdrawer import AppDrawer
from widgets.bgselector import BgSelector
from widgets.controlcenter import ControlCenter
from widgets.notificationsosd import NotificationsOSD
from widgets.volumeosd import VolumeOSD

if __name__ == "__main__":
    app = Application("bombshell", open_inspector=False)

                                                                                  
    app.app_drawer = AppDrawer()
    app.bg_selector = BgSelector()
    app.control_center = ControlCenter()
    app.notifications = NotificationsOSD()
    app.volume_osd = VolumeOSD()

    windows = [
        app.app_drawer,
        app.bg_selector,
        app.control_center,
        app.notifications,
        app.volume_osd,
    ]
    for window in windows:
        app.add_window(window)

    app.set_stylesheet_from_file(config.style_sheet)
    app.run()
