from typing import Any, List, Literal
import gi
from fabric.core.service import Property, Service, Signal
from fabric.utils import bulk_connect, exec_shell_command_async
from gi.repository import Gio
from loguru import logger

try:
    gi.require_version("NM", "1.0")
    from gi.repository import NM
except ValueError:
    logger.error("Failed to start network manager")


class Wifi(Service):
    """A service to manage the wifi connection."""

    @Signal
    def changed(self) -> None: ...

    def __init__(self, client: NM.Client, device: NM.DeviceWifi, **kwargs):
        self._client: NM.Client = client
        self._device: NM.DeviceWifi = device
        self._ap: NM.AccessPoint | None = None
        self._ap_signal: int | None = None
        self._last_active_bssid: str | None = None
        super().__init__(**kwargs)

        self._client.connect(
            "notify::wireless-enabled",
            lambda *args: self.notifier("enabled", args),
        )
        if self._device:
            bulk_connect(
                self._device,
                {
                    "notify::active-access-point": lambda *args: self.activate_ap(),
                    "access-point-added": lambda *args: self.emit("changed"),
                    "access-point-removed": lambda *args: self.emit("changed"),
                    "state-changed": lambda *args: self.ap_update(),
                },
            )
            self.activate_ap()

    def ap_update(self):
        print(
            "[wifi-service] ap_update",
            {
                "state": self.state,
                "active_bssid": self.active_bssid,
                "ssid": self.ssid,
                "access_points": len(self._device.get_access_points()),
            },
        )
        self.emit("changed")
        for sn in [
            "enabled",
            "internet",
            "strength",
            "frequency",
            "access-points",
            "ssid",
            "state",
            "icon-name",
        ]:
            self.notify(sn)

    def activate_ap(self):
        if self._ap:
            self._ap.disconnect(self._ap_signal)
        self._ap = self._device.get_active_access_point()
        print(
            "[wifi-service] active-ap",
            {
                "active_ap": self._ap.get_bssid() if self._ap else None,
                "device_state": self._device.get_state(),
            },
        )
        if not self._ap:
            return
        self._last_active_bssid = self._ap.get_bssid()

    def toggle_wifi(self):
        self._client.wireless_set_enabled(not self._client.wireless_get_enabled())

    def disconnect(self):
        active_connection = self._device.get_active_connection()
        if not active_connection:
            return
        iface = self._device.get_iface()
        if iface:
            exec_shell_command_async(
                f"nmcli device disconnect {iface}",
                lambda *args: print(args),
            )

                                  
                             

    def has_saved_connection(self, ssid: str, secured: bool = False) -> bool:
        if not ssid:
            return False
        for conn in self._client.get_connections():
            s_wifi = conn.get_setting_wireless()
            if s_wifi and s_wifi.get_ssid():
                conn_ssid = NM.utils_ssid_to_utf8(s_wifi.get_ssid().get_data())
                if conn_ssid == ssid:
                    if not secured:
                        return True
                    s_wsec = conn.get_setting_wireless_security()
                    if not s_wsec:
                        continue
                    if (
                        s_wsec.get_psk()
                        or s_wsec.get_wep_key(0)
                        or s_wsec.get_leap_password()
                    ):
                        return True
                    continue
        return False

    def scan(self):
        self._device.request_scan_async(
            None,
            lambda device, result: [
                device.request_scan_finish(result),
                self.emit("changed"),
            ],
        )

    def notifier(self, name: str, *args):
        self.notify(name)
        self.emit("changed")
        return

    @Property(bool, "read-write", default_value=False)
    def enabled(self) -> bool:                
        return bool(self._client.wireless_get_enabled())

    @enabled.setter
    def enabled(self, value: bool):
        self._client.wireless_set_enabled(value)

    @Property(int, "readable")
    def strength(self):
        return self._ap.get_strength() if self._ap else -1

    @Property(str, "readable")
    def icon_name(self):
        if not self._ap:
            return "network-wireless-disabled-symbolic"

        if self.internet == "activated":
            return {
                80: "network-wireless-signal-excellent-symbolic",
                60: "network-wireless-signal-good-symbolic",
                40: "network-wireless-signal-ok-symbolic",
                20: "network-wireless-signal-weak-symbolic",
                00: "network-wireless-signal-none-symbolic",
            }.get(
                min(80, 20 * round(self._ap.get_strength() / 20)),
                "network-wireless-no-route-symbolic",
            )
        if self.internet == "activating":
            return "network-wireless-acquiring-symbolic"

        return "network-wireless-offline-symbolic"

    @Property(int, "readable")
    def frequency(self):
        return self._ap.get_frequency() if self._ap else -1

    @Property(int, "readable")
    def internet(self):
        return {
            NM.ActiveConnectionState.ACTIVATED: "activated",
            NM.ActiveConnectionState.ACTIVATING: "activating",
            NM.ActiveConnectionState.DEACTIVATING: "deactivating",
            NM.ActiveConnectionState.DEACTIVATED: "deactivated",
        }.get(
            self._device.get_active_connection().get_state(),
            "unknown",
        )

    @Property(object, "readable")
    def access_points(self) -> List[object]:
        points: list[NM.AccessPoint] = self._device.get_access_points()
        ap_flags = getattr(NM, "80211ApFlags")

        def make_ap_dict(ap: NM.AccessPoint):
            ssid = (
                NM.utils_ssid_to_utf8(ap.get_ssid().get_data()) if ap.get_ssid() else ""
            )
            secured = (
                bool(ap.get_flags() & ap_flags.PRIVACY)
                or bool(ap.get_rsn_flags())
                or bool(ap.get_wpa_flags())
            )
            return {
                "bssid": ap.get_bssid(),
                                    
                "last_seen": ap.get_last_seen(),
                "ssid": ssid,
                "active-ap": self.active_bssid,
                "strength": ap.get_strength(),
                "frequency": ap.get_frequency(),
                "secured": secured,
                "has-profile": self.has_saved_connection(ssid, secured=secured)
                if secured
                else False,
                "icon-name": {
                    80: "network-wireless-signal-excellent-symbolic",
                    60: "network-wireless-signal-good-symbolic",
                    40: "network-wireless-signal-ok-symbolic",
                    20: "network-wireless-signal-weak-symbolic",
                    00: "network-wireless-signal-none-symbolic",
                }.get(
                    min(80, 20 * round(ap.get_strength() / 20)),
                    "network-wireless-no-route-symbolic",
                ),
            }

        return list(map(make_ap_dict, points))

    @Property(str, "readable")
    def ssid(self):
        if not self._ap:
            return "Disconnected"
        ssid = self._ap.get_ssid().get_data()
        return NM.utils_ssid_to_utf8(ssid) if ssid else "Unknown"

    @Property(str, "readable")
    def active_bssid(self):
        if self._ap:
            return self._ap.get_bssid()
        return self._last_active_bssid

    @Property(int, "readable")
    def state(self):
        return {
            NM.DeviceState.UNMANAGED: "unmanaged",
            NM.DeviceState.UNAVAILABLE: "unavailable",
            NM.DeviceState.DISCONNECTED: "disconnected",
            NM.DeviceState.PREPARE: "prepare",
            NM.DeviceState.CONFIG: "config",
            NM.DeviceState.NEED_AUTH: "need_auth",
            NM.DeviceState.IP_CONFIG: "ip_config",
            NM.DeviceState.IP_CHECK: "ip_check",
            NM.DeviceState.SECONDARIES: "secondaries",
            NM.DeviceState.ACTIVATED: "activated",
            NM.DeviceState.DEACTIVATING: "deactivating",
            NM.DeviceState.FAILED: "failed",
        }.get(self._device.get_state(), "unknown")


class Ethernet(Service):
    """A service to manage the ethernet connection."""

    @Signal
    def changed(self) -> None: ...

    @Signal
    def enabled(self) -> bool: ...

    @Property(int, "readable")
    def speed(self) -> int:
        return self._device.get_speed()

    @Property(str, "readable")
    def internet(self) -> str:
        return {
            NM.ActiveConnectionState.ACTIVATED: "activated",
            NM.ActiveConnectionState.ACTIVATING: "activating",
            NM.ActiveConnectionState.DEACTIVATING: "deactivating",
            NM.ActiveConnectionState.DEACTIVATED: "deactivated",
        }.get(
            self._device.get_active_connection().get_state(),
            "disconnected",
        )

    @Property(str, "readable")
    def icon_name(self) -> str:
        network = self.internet
        if network == "activated":
            return "network-wired-symbolic"

        elif network == "activating":
            return "network-wired-acquiring-symbolic"

        elif self._device.get_connectivity != NM.ConnectivityState.FULL:
            return "network-wired-no-route-symbolic"

        return "network-wired-disconnected-symbolic"

    def __init__(self, client: NM.Client, device: NM.DeviceEthernet, **kwargs) -> None:
        super().__init__(**kwargs)
        self._client: NM.Client = client
        self._device: NM.DeviceEthernet = device

        for pn in (
            "active-connection",
            "icon-name",
            "internet",
            "speed",
            "state",
        ):
            self._device.connect(f"notify::{pn}", lambda *_: self.notifier(pn))

        self._device.connect("notify::speed", lambda *_: print(_))

    def notifier(self, pn):
        self.notify(pn)
        self.emit("changed")


class NetworkClient(Service):
    """A service to manage the network connections."""

    @Signal
    def device_ready(self) -> None: ...

    def __init__(self, **kwargs):
        self._client: NM.Client | None = None
        self.wifi_device: Wifi | None = None
        self.ethernet_device: Ethernet | None = None
        super().__init__(**kwargs)
        NM.Client.new_async(
            cancellable=None,
            callback=self.init_network_client,
            **kwargs,
        )

    def init_network_client(self, client: NM.Client, task: Gio.Task, **kwargs):
        self._client = client
        wifi_device: NM.DeviceWifi | None = self.get_device(NM.DeviceType.WIFI)                
        ethernet_device: NM.DeviceEthernet | None = self.get_device(
            NM.DeviceType.ETHERNET
        )

        if wifi_device:
            self.wifi_device = Wifi(self._client, wifi_device)
            self.emit("device-ready")

        if ethernet_device:
            self.ethernet_device = Ethernet(client=self._client, device=ethernet_device)
            self.emit("device-ready")

        self.notify("primary-device")

    def get_device(self, device_type) -> Any:
        devices: List[NM.Device] = self._client.get_devices()                
        return next(
            (
                x
                for x in devices
                if x.get_device_type() == device_type
                and x.get_active_connection() is not None
            ),
            None,
        )

    def get_primary_device(self) -> Literal["wifi", "wired"] | None:
        if not self._client:
            return None
        return (
            "wifi"
            if "wireless"
            in str(self._client.get_primary_connection().get_connection_type())
            else "wired"
            if "ethernet"
            in str(self._client.get_primary_connection().get_connection_type())
            else None
        )

    def connect_wifi_bssid(self, bssid, password=None):
                                              
        cmd = f"nmcli device wifi connect {bssid}"
        if password:
            cmd += f" password {password}"
        exec_shell_command_async(cmd, lambda *args: print(args))

    def disconnect_wifi(self):
        if self.wifi_device:
            self.wifi_device.disconnect()

    @Property(str, "readable")
    def primary_device(self) -> Literal["wifi", "wired"] | None:
        return self.get_primary_device()
