import flet as ft
import time
from typing import Optional

@ft.control("flet_contact_launcher")
class FletContactLauncher(ft.Service):
    phone_to_open: str = ""
    request_id: str = ""
    on_status: Optional[ft.ControlEventHandler["FletContactLauncher"]] = None

    def open_contact(self, phone: str) -> str:
        request_id = str(time.time_ns())
        self.phone_to_open = phone
        self.request_id = request_id
        self.update()
        return request_id


class ContactLauncherError(Exception):
    pass
