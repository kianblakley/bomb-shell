from services.bootstrap import niri_service
from fabric import Application
from fabric.widgets.wayland import WaylandWindow
from fabric.widgets.box import Box
from fabric.widgets.revealer import Revealer
from fabric.widgets.label import Label
from fabric.widgets.flowbox import FlowBox
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.image import Image
from fabric.widgets.entry import Entry
from fabric.utils import get_desktop_applications, invoke_repeater, idle_add
from utils.config import config
from rapidfuzz import fuzz, utils
from pathlib import Path
import json
import math

SCREEN_SIZE = niri_service.get_screen_size()
APPS_PER_ROW = 8


class AppDrawer(WaylandWindow):
    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay",
            anchor="top bottom left right",
            keyboard_mode="none",
            pass_through=True,
            **kwargs,
        )
        self.setup_state()
        self.build_ui()
        self.populate_apps()
        self.load_search_history()
        self.connect_signals()

    def setup_state(self):
        self.desktop_apps = get_desktop_applications()
        self.mapped_children = []
        self.fuzzy_scores = {}
        self.selected_index = 0
        self.search_history_path = config.search_history_path

    def build_ui(self):
        self.search_icon = Label(label="")
        self.entry = (
            Entry(placeholder="Search:")
            .build()
            .set_max_width_chars(32)
            .connect("changed", self.filter_apps)
            .set_can_focus(False)
            .unwrap()
        )

        self.search_bar = Box(
            children=[self.search_icon, self.entry],
            h_align="center",
            spacing=10,
            name="appdrawer-searchbar",
        )
        self.flow_box = (
            FlowBox(name="appdrawer-flowbox", v_align="start")
            .build()
            .set_max_children_per_line(APPS_PER_ROW)
            .set_row_spacing(0)
            .set_column_spacing(0)
            .set_homogeneous(True)
            .connect("child-activated", self.on_app_activated)
            .set_activate_on_single_click(False)
            .unwrap()
        )

        scroll_width = math.ceil(SCREEN_SIZE[0] * 0.8)
        scroll_height = math.ceil(SCREEN_SIZE[1] * 0.64)

        self.scrolled_window = ScrolledWindow(
            min_content_size=(scroll_width, scroll_height),
            max_content_size=(scroll_width, scroll_height),
            child=self.flow_box,
            name="appdrawer-viewport",
            h_align="center",
        )

        spacing = math.ceil(SCREEN_SIZE[1] * 0.05)

        self.main_container = Box(
            size=SCREEN_SIZE,
            orientation="v",
            children=[
                Box(v_expand=True),
                self.search_bar,
                self.scrolled_window,
                Box(v_expand=True),
            ],
            spacing=spacing,
            name="appdrawer-main",
        )

        self.revealer = Revealer(
            transition_type="crossfade",
            transition_duration=200,
            child=self.main_container,
            v_align="end",
        )

        self.revealer_container = Box(
            size=SCREEN_SIZE,
            children=self.revealer,
            v_align="fill",
            h_align="fill",
            name="appdrawer-background",
        )
        self.add(self.revealer_container)

    def populate_apps(self):
        for desktop_app in self.desktop_apps:
            self.flow_box.add(AppTile(desktop_app))

    def load_search_history(self):
        try:
            self.search_history_path.touch(exist_ok=False)
            with self.search_history_path.open("w") as f:
                json.dump({}, f)
        except Exception:
            pass
        self.refresh_search_history()
        self.flow_box.set_sort_func(self.history_sort)

    def connect_signals(self):
        self.connect("key-press-event", self.on_key_press)

    def update_mapped_children(self):
        self.mapped_children = [
            child for child in self.flow_box.get_children() if child.get_mapped()
        ]

    def on_app_activated(self, _, child):
        app = child.get_child().app_data
        app.launch()
        with self.search_history_path.open("r+") as f:
            search_history = json.load(f)
            search_history[app.name] = search_history.get(app.name, 0) + 1
            f.seek(0)
            json.dump(search_history, f)
            f.truncate()
        self.toggle()

    def on_key_press(self, _, event):
        key = event.keyval
        if key == 65307:
            self.toggle()
        elif key == 65293:
            self.handle_enter()
        elif key in range(65361, 65365):
            self.handle_arrow(key)
        else:
            self.entry.event(event)
        return True

    def handle_enter(self):
        self.update_mapped_children()
        if self.mapped_children and self.selected_index < len(self.mapped_children):
            self.mapped_children[self.selected_index].activate()

    def handle_arrow(self, arrow_key):
        self.update_mapped_children()
        if not self.mapped_children:
            return
        max_index = len(self.mapped_children) - 1
        match arrow_key:
            case 65363:
                self.selected_index += 1
                if self.selected_index > max_index:
                    self.selected_index = 0
            case 65361:
                self.selected_index -= 1
                if self.selected_index < 0:
                    self.selected_index = max_index
            case 65364:
                self.selected_index += APPS_PER_ROW
                if self.selected_index > max_index:
                    self.selected_index = 0
            case 65362:
                self.selected_index -= APPS_PER_ROW
                if self.selected_index < 0:
                    self.selected_index = max_index

        self.selected_index = max(0, min(self.selected_index, max_index))
        self.flow_box.select_child(self.mapped_children[self.selected_index])
        self.scroll_to_selection()

    def scroll_to_selection(self):
        if not self.mapped_children:
            return
        selected = self.mapped_children[self.selected_index]
        adj = self.scrolled_window.get_vadjustment()
        alloc = selected.get_allocation()
        child_y = alloc.y
        child_height = alloc.height
        page_size = adj.get_page_size()
        current_val = adj.get_value()
        if child_y + child_height > current_val + page_size:
            adj.set_value(child_y + child_height - page_size)
        elif child_y < current_val:
            adj.set_value(child_y)

    def history_sort(self, child1, child2):
        name1 = child1.get_child().app_data.name
        name2 = child2.get_child().app_data.name
        h1 = self.search_history.get(name1, 0)
        h2 = self.search_history.get(name2, 0)
        return h2 - h1

    def filter_apps(self, _):
        query = self.entry.get_text()

        def fuzzy_filter(child):
            fuzzy_score = fuzz.WRatio(
                query,
                child.get_child().app_data.name,
                processor=utils.default_process,
                score_cutoff=60,
            )
            self.fuzzy_scores[child] = fuzzy_score
            return fuzzy_score != 0

        def fuzzy_sort(child1, child2):
            child1_fuzzy_score = self.fuzzy_scores.get(child1, 0)
            child2_fuzzy_score = self.fuzzy_scores.get(child2, 0)
            return child2_fuzzy_score - child1_fuzzy_score

        if query:
            self.flow_box.set_filter_func(fuzzy_filter)
            self.flow_box.set_sort_func(fuzzy_sort)
        else:
            self.flow_box.set_filter_func(None)
            self.flow_box.set_sort_func(self.history_sort)
        self.select_first_child()

    def refresh_search_history(self):
        with self.search_history_path.open("r+") as f:
            search_history = json.load(f)
            for child in self.flow_box.get_children():
                child_name = child.get_child().app_data.name
                if child_name not in search_history:
                    search_history[child_name] = 0
            f.seek(0)
            json.dump(search_history, f)
            f.truncate()
            self.search_history = search_history

    def toggle(self):
        if self.revealer.child_revealed:
            self.revealer.unreveal()
            self.set_keyboard_mode("none")
            self.set_pass_through(True)
            invoke_repeater(
                150,
                lambda: (self.entry.set_text(""), self.select_first_child(), False)[2],
                initial_call=False,
            )
        else:
            self.set_pass_through(False)
            self.revealer.reveal()
            self.set_keyboard_mode("exclusive")
            self.entry.grab_focus()

    def select_first_child(self):
        self.update_mapped_children()
        if self.mapped_children:
            print(self.mapped_children)
            self.flow_box.select_child(self.mapped_children[0])
            self.selected_index = 0
            self.scrolled_window.get_vadjustment().set_value(0)


class AppTile(Box):
    def __init__(self, app, **kwargs):
        super().__init__(
            name="appdrawer-app",
            orientation="v",
            spacing=12,
            **kwargs,
        )
        self.app_data = app
        self.icon = Image(
            pixbuf=app.get_icon_pixbuf(),
            size=config.icon_sizes[4],
            name="appdrawer-icon",
        )
        self.label = Label(
            label=self.truncate_label(app.name),
            v_expand=False,
            name="appdrawer-label",
            h_expand=False,
        )
        self.add(self.icon)
        self.add(self.label)

    def truncate_label(self, label):
        if len(label) > 11:
            return label[:9].rstrip(" ") + "..."
        return label


if __name__ == "__main__":
    app_drawer = AppDrawer()
    app = Application("appdrawer", app_drawer, open_inspector=False)
    app.set_stylesheet_from_file(config.style_sheet.with_name("appdrawer.css"))
    app.run()
