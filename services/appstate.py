from fabric.core.service import Property, Service, Signal


class AppState(Service):
    __gtype_name__ = "AppState"

    @Signal
    def dnd_changed(self, value: bool) -> None: ...

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dnd = False

    @Property(bool, "read-write", default_value=False)
    def dnd(self) -> bool:
        return self._dnd

    @dnd.setter
    def dnd(self, value: bool):
        self._dnd = value
        self.emit("dnd-changed", value)
