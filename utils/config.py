import json
from pathlib import Path

class Config:
    def __init__(self):
        self.bomb_shell_root = Path(__file__).resolve().parent.parent
        self.settings = {}
        try:
            with open(self.bomb_shell_root / "config.json", "r") as f:
                self.settings = json.load(f)
        except Exception as e:
            print(e)
            
        self.style_sheet = self.bomb_shell_root / "styles" / ("transparent" if self.get_setting("transparency") else "opaque") / "main.css" 

        self.home_dir = Path("~/").expanduser()
        self.cache_dir = self.home_dir / ".cache/bomb-shell/"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.blurred_dir = self.cache_dir / "blurred/"
        self.blurred_dir.mkdir(exist_ok=True, parents=True)

        self.thumbnails_dir = self.cache_dir / "thumbnails/"
        self.thumbnails_dir.mkdir(exist_ok=True, parents=True)

        self.notifications_path = self.cache_dir / "notifications.json"
        if not self.notifications_path.exists():
            with open(self.notifications_path, "w") as f:
                json.dump([], f)

        self.search_history_path = self.cache_dir / "search_history.json"
        if not self.search_history_path.exists():
    	    with open(self.search_history_path, "w") as f:
                json.dump({}, f)

        self.icon_sizes = [12,14,18,20,24,35,54]
        self.corner_size = 12
    
    def get_setting(self, key):
        setting = self.settings[key]
        if isinstance(setting, str) and setting.startswith("~"):
            return Path(setting).expanduser()
        return setting

config = Config()
