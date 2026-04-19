from services.bootstrap import niri_service
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from fabric import Application
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.image import Image
from fabric.widgets.revealer import Revealer
from pathlib import Path
from PIL import Image as PILImage
from PIL import ImageFilter
from PIL import ImageOps
from utils.animator import Animator
from utils.config import config
import math
import subprocess

SCREEN_SIZE = niri_service.get_screen_size()
WALLPAPER_PATH = Path(config.get_setting("wallpapers_path"))
THUMBNAIL_PATH = config.thumbnails_dir
BLURRED_PATH = config.blurred_dir
SPACING = 20
WALLPAPERS_PER_PAGE = 5
THUMBNAIL_SIZE = (
    (SCREEN_SIZE[0] / WALLPAPERS_PER_PAGE)
    - (SPACING * (WALLPAPERS_PER_PAGE - 1)) / WALLPAPERS_PER_PAGE,
    math.ceil(SCREEN_SIZE[1] / 2),
)
SLOWNESS_FACTOR = 5.5


class BgSelector(WaylandWindow):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay",
            anchor="top bottom left right",
            keyboard_mode="none",
            pass_through=True,
            **kwargs,
        )
        self.setup_state()
        self.prepare_wallpaper_assets()
        self.build_ui()
        self.connect_signals()
        self.scroll_to_centered_wallpaper()

    def setup_state(self):
        self.enable_parallax = True
        self.centered_index = 0
        self.previous_carousel_value = 0

    def prepare_wallpaper_assets(self):
        for path in Path(WALLPAPER_PATH).iterdir():
            if path.is_file():
                try:
                    source_image = PILImage.open(str(path))
                    blurred_img = source_image.filter(ImageFilter.GaussianBlur(5))
                    blurred_img.save(BLURRED_PATH / path.name)
                    resized_img = ImageOps.cover(source_image, THUMBNAIL_SIZE, 1)
                    resized_img.save(THUMBNAIL_PATH / path.name)
                except Exception:
                    pass

    def build_ui(self):
        self.wallpaper_list = Box(
            size=(SCREEN_SIZE[0], THUMBNAIL_SIZE[1]),
            v_align="center",
            h_align="center",
            orientation="h",
            spacing=SPACING,
            name="bgselector-wallpapers-container",
        )

        for wallpaper_file in sorted(Path(config.thumbnails_dir).iterdir()):
            if wallpaper_file.is_file():
                wallpaper_item = ScrolledWindow(
                    child=Image(
                        image_file=str(wallpaper_file),
                        h_align="fill",
                        name=wallpaper_file.name,
                    ),
                    min_content_size=THUMBNAIL_SIZE,
                    max_content_size=THUMBNAIL_SIZE,
                    name="bgselector-wallpaper-item",
                    h_align="center",
                    v_align="center",
                    v_scrollbar_policy="never",
                    h_scrollbar_policy="always",
                    overlay_scroll=True,
                )
                self.wallpaper_list.add(wallpaper_item)

        self.carousel_scroll = ScrolledWindow(
            min_content_size=(SCREEN_SIZE[0], THUMBNAIL_SIZE[1]),
            max_content_size=(SCREEN_SIZE[0], THUMBNAIL_SIZE[1]),
            name="bgselector-carousel",
            child=self.wallpaper_list,
            h_align="center",
            v_align="center",
            v_scrollbar_policy="never",
            h_scrollbar_policy="always",
            overlay_scroll=False,
        )
        self.carousel_adjustment = self.carousel_scroll.get_hadjustment()
        self.animator = Animator(
            bezier_curve=(0.34, 1.56, 0.64, 1.0),
            duration=0.8,
            tick_widget=self,
            notify_value=lambda animator, *_: self.carousel_adjustment.set_value(
                animator.value
            ),
        )

        self.centered_index = max(0, math.ceil(len(self.wallpaper_list) / 2) - 1)
        self.previous_carousel_value = self.carousel_adjustment.get_value()

        self.main_container = Box(
            size=SCREEN_SIZE,
            name="bgselector-main",
            spacing=SPACING,
            children=[self.carousel_scroll],
            h_align="center",
            v_align="center",
        )

        self.revealer = Revealer(
            transition_type="crossfade",
            transition_duration=200,
            child=self.main_container,
            v_align="end",
        )

        self.revealer_container = Box(
            size=SCREEN_SIZE,
            children=[self.revealer],
            v_align="fill",
            h_align="fill",
            name="bgselector-revealer-container",
        )

        self.add(self.revealer_container)

    def connect_signals(self):
        self.connect("key-press-event", self.on_key_press)
        self.carousel_adjustment.connect("value-changed", self.on_navigate)

    def scroll_to_centered_wallpaper(self):
        self.animator.pause()
        target_value = (
            (self.centered_index * THUMBNAIL_SIZE[0])
            + (self.centered_index * SPACING)
            + (THUMBNAIL_SIZE[0] / 2)
            - (SCREEN_SIZE[0] / 2)
        )
        current_value = self.carousel_adjustment.get_value()
        self.animator.min_value = current_value
        self.animator.max_value = target_value
        self.animator.play()

    def cycle_carousel(self, direction):
        self.enable_parallax = False
        current_value = self.carousel_adjustment.get_value()
        match direction:
            case "right":
                tail = self.wallpaper_list.get_children()[0]
                self.wallpaper_list.reorder_child(tail, -1)
                self.carousel_adjustment.set_value(
                    current_value - THUMBNAIL_SIZE[0] - SPACING
                )
            case "left":
                tail = self.wallpaper_list.get_children()[-1]
                self.wallpaper_list.reorder_child(tail, 0)
                self.carousel_adjustment.set_value(
                    current_value + THUMBNAIL_SIZE[0] + SPACING
                )
        self.enable_parallax = True

    def on_navigate(self, carousel_adjustment):
        new_carousel_value = carousel_adjustment.get_value()
        if self.enable_parallax:
            for i, adj in enumerate(
                [
                    wallpaper.get_hadjustment()
                    for wallpaper in self.wallpaper_list.get_children()
                ]
            ):
                if i in range(
                    self.centered_index - math.ceil(WALLPAPERS_PER_PAGE / 2),
                    self.centered_index + math.ceil(WALLPAPERS_PER_PAGE / 2) + 1,
                ):
                    carousel_change = new_carousel_value - self.previous_carousel_value
                    current_wallpaper_value = adj.get_value()
                    adj.set_value(
                        current_wallpaper_value + carousel_change / SLOWNESS_FACTOR
                    )
                elif i < self.centered_index:
                    adj.set_value(adj.get_upper() - adj.get_page_size())
                else:
                    adj.set_value(0)
        self.previous_carousel_value = new_carousel_value

    def on_key_press(self, _, event):
        key = event.keyval
        if key == 65307:
            self.toggle()
        elif key == 65293:
            self.handle_enter()
        elif key in range(65361, 65365):
            self.handle_arrow(key)
        return True

    def handle_enter(self):
        children = self.wallpaper_list.get_children()
        if not children:
            return
        file_name = children[self.centered_index].get_child().get_child().get_name()
        subprocess.run(
            [
                "awww",
                "img",
                WALLPAPER_PATH / file_name,
                "-t",
                "grow",
                "--transition-duration",
                "1",
                "--transition-fps",
                "75",
                "-n",
                "workspaces",
            ]
        )
        subprocess.run(
            [
                "awww",
                "img",
                BLURRED_PATH / file_name,
                "-t",
                "grow",
                "--transition-duration",
                "1",
                "--transition-fps",
                "75",
                "-n",
                "overview",
            ]
        )
        self.toggle()

    def handle_arrow(self, arrow_key):
        match arrow_key:
            case 65363:
                self.cycle_carousel("right")
                self.scroll_to_centered_wallpaper()
            case 65361:
                self.cycle_carousel("left")
                self.scroll_to_centered_wallpaper()

    def toggle(self):
        if self.revealer.child_revealed:
            self.revealer.unreveal()
            self.set_keyboard_mode("none")
            self.set_pass_through(True)
        else:
            self.set_pass_through(False)
            self.revealer.reveal()
            self.set_keyboard_mode("exclusive")


if __name__ == "__main__":
    bg_selector = BgSelector()
    app = Application("bgselector", bg_selector, open_inspector=False)
    app.set_stylesheet_from_file(config.style_sheet.with_name("bgselector.css"))
    app.run()
