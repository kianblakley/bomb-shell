from fabric.audio.service import Audio
from fabric.bluetooth.service import BluetoothClient
from fabric.notifications.service import Notifications
from services.network import NetworkClient
from services.niri import NiriClient
from services.upower import UPowerManager
from services.appstate import AppState

audio_service = Audio()
bluetooth_service = BluetoothClient()
notifications_service = Notifications()
network_service = NetworkClient()
upower_service = UPowerManager()
niri_service = NiriClient()
app_state = AppState()

