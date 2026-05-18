import os
import sys
import json
import asyncio
from datetime import date, datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

LOCAL_CONTACT_PACKAGE = os.path.join(os.path.dirname(__file__), "packages", "flet_contact_launcher")
if os.path.isdir(LOCAL_CONTACT_PACKAGE) and LOCAL_CONTACT_PACKAGE not in sys.path:
    sys.path.insert(0, LOCAL_CONTACT_PACKAGE)
LOCAL_STT_PACKAGE = os.path.join(os.path.dirname(__file__), "packages", "flet_stt")
if os.path.isdir(LOCAL_STT_PACKAGE) and LOCAL_STT_PACKAGE not in sys.path:
    sys.path.insert(0, LOCAL_STT_PACKAGE)

import flet as ft
try:
    from flet_stt import FletStt, SttError, SttErrorData, SttResult, SttStatus
except ImportError:
    FletStt = None

    class SttError(Exception):
        pass

try:
    from flet_contact_launcher import ContactLauncherError, FletContactLauncher
except ImportError:
    FletContactLauncher = None

    class ContactLauncherError(Exception):
        pass

from components.calendar import CalendarComponent
from components.time_picker import create_time_picker
from utils.date_parser import parse_datetime_from_text
from utils.storage import init_storage, load_tasks, save_tasks
from utils.supabase_service import sign_in_with_password, sign_up
from utils.sync import sync_once
from utils.session import clear_session, init_session_storage, load_session, save_session


def format_date_display(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%d.%m")


def format_date_full(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    months = [
        "",
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]
    weekdays = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]
    return f"{weekdays[d.weekday()]}, {d.day} {months[d.month]} {d.year}"


def _static_osm_map_url(lat: float, lon: float, width: int = 320, height: int = 320, zoom: int = 16) -> str:
    lat_s = f"{lat:.6f}"
    lon_s = f"{lon:.6f}"
    width = max(1, min(int(width), 650))
    height = max(1, min(int(height), 450))
    size = f"{width},{height}"
    # Static mini-map: always show Simferopol city overview, place marker at task coordinates.
    # Center: Simferopol (approx.)
    city_ll = "34.1108,44.9521"
    city_zoom = 11
    return f"https://static-maps.yandex.ru/1.x/?ll={city_ll}&size={size}&z={city_zoom}&l=map&pt={lon_s},{lat_s},pm2rdm"
    

TASK_SECTIONS = [
    ("morning", "Утро"),
    ("day", "День"),
    ("evening", "Вечер"),
]
TASK_SECTION_LABELS = dict(TASK_SECTIONS)


async def main(page: ft.Page):
    page.title = "Мои задачи"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 30
    page.scroll = ft.ScrollMode.AUTO

    fullscreen_map_url: str | None = None

    root_view = ft.View(route="/", controls=[], scroll=ft.ScrollMode.AUTO)
    page.views.clear()
    page.views.append(root_view)

    def root_controls():
        return page.views[0].controls

    selected_date = date.today().strftime("%Y-%m-%d")
    selected_time = ""
    selected_section = "day"
    dragging_task_id = ""

    storage_paths = ft.StoragePaths()
    try:
        db_dir = await storage_paths.get_library_directory()
    except Exception:
        db_dir = os.path.dirname(__file__)

    db_path = os.path.join(db_dir, "tasks.db")
    init_storage(db_path)

    init_session_storage(db_dir)
    session_data = load_session()

    tasks = load_tasks()

    access_token = session_data.get("access_token")
    user_id = session_data.get("user_id")

    task_list = ft.Column(spacing=10)
    stt = FletStt() if FletStt else None
    contact_launcher = FletContactLauncher() if FletContactLauncher else None
    stt_available = stt is not None
    stt_initialized = False
    selected_stt_locale = ""
    voice_target: ft.TextField | None = None
    voice_base_text = ""
    voice_button: ft.IconButton | None = None
    voice_listening = False
    pending_contact_requests: dict[str, str] = {}

    def show_snackbar(msg: str):
        sb = ft.SnackBar(content=ft.Text(msg))
        page.overlay.append(sb)
        sb.open = True
        page.update()

    if stt is not None:
        page.services.append(stt)
    if contact_launcher is not None:
        page.services.append(contact_launcher)

    def parse_event_payload(data):
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {"status": data}
        return {}

    def on_contact_launcher_status(e: ft.ControlEvent):
        payload = parse_event_payload(e.data)
        status = str(payload.get("status", "")).strip()
        request_id = str(payload.get("request_id", "")).strip()
        phone = str(payload.get("phone", "")).strip()

        if request_id:
            pending_contact_requests.pop(request_id, None)

        if not status or status.startswith("opened_"):
            return
        if status == "not_found":
            show_snackbar("Контакт с таким номером не найден в телефонной книге")
            return
        if status.startswith("permission_denied"):
            show_snackbar("Разрешите доступ к контактам в настройках приложения")
            return
        if status.startswith("launch_failed:"):
            details = status.split(":", 1)[1]
            show_snackbar(f"Телефонная книга не открыла контакт: {details}")
            return
        if status.startswith("error:"):
            details = status.split(":", 1)[1]
            show_snackbar(f"Ошибка открытия контакта: {details}")
            return
        show_snackbar(f"Не удалось открыть контакт {phone or ''}: {status}".strip())

    if contact_launcher is not None:
        contact_launcher.on_status = on_contact_launcher_status

    def open_map_image(url: str | None):
        nonlocal fullscreen_map_url
        if not url:
            return
        fullscreen_map_url = url
        page.go("/map")

    def build_map_view() -> ft.View:
        nonlocal fullscreen_map_url
        url = fullscreen_map_url
        img = ft.Image(
            src=url or "",
            width=650,
            height=450,
            fit=ft.ImageFit.CONTAIN if hasattr(ft, "ImageFit") else "contain",
            error_content=ft.Text(
                "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РєР°СЂС‚Сѓ",
                color=ft.Colors.WHITE,
                size=16,
            ),
        )

        viewer_cls = getattr(ft, "InteractiveViewer", None)
        content: ft.Control
        if viewer_cls:
            try:
                content = viewer_cls(content=img, expand=True, min_scale=0.5, max_scale=4)
            except Exception:
                content = img
        else:
            content = img

        return ft.View(
            route="/map",
            controls=[
                ft.AppBar(
                    title=ft.Text("Карта"),
                    leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/")),
                ),
                ft.Container(content=content, expand=True, bgcolor=ft.Colors.BLACK),
            ],
            padding=0,
        )

    def route_change(e=None):
        if page.route == "/map":
            if len(page.views) == 1 or page.views[-1].route != "/map":
                page.views.append(build_map_view())
        else:
            while len(page.views) > 1:
                page.views.pop()
        page.update()

    def view_pop(e: ft.ViewPopEvent):
        page.views.pop()
        page.go(page.views[-1].route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    def open_url(url: str | None):
        if not url:
            return
        try:
            res = page.launch_url(url)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
                return
            return
        except Exception:
            pass
        try:
            ft.launch_url(url)
        except Exception as ex:
            show_snackbar(f"Не удалось открыть ссылку: {ex}")

    def open_contact_by_phone(raw_phone: str | None):
        raw_phone = (raw_phone or "").strip()
        if not raw_phone:
            show_snackbar("Введите номер телефона")
            return

        normalized = "".join(ch for ch in raw_phone if ch.isdigit() or ch in "+*#")
        if not normalized:
            show_snackbar("Некорректный номер телефона")
            return

        show_snackbar("Открываю контакт...")

        async def try_open_contact():
            if contact_launcher is None:
                show_snackbar("Нативный запуск контактов недоступен. Пересоберите APK.")
                return
            try:
                result = await asyncio.wait_for(
                    contact_launcher.open_contact(normalized),
                    timeout=8,
                )
            except asyncio.TimeoutError:
                show_snackbar("Не удалось получить ответ от телефонной книги")
                return
            except ContactLauncherError as ex:
                show_snackbar(f"Не удалось открыть контакт: {ex}")
                return

            if result.startswith("opened") or result == "started":
                return
            if result == "not_found":
                show_snackbar("Контакт с таким номером не найден")
                return
            if result == "permission_denied":
                show_snackbar("Разрешите доступ к контактам в настройках приложения")
                return
            show_snackbar(f"Не удалось открыть контакт: {result}")

        page.run_task(try_open_contact)

    def open_contact_by_phone(raw_phone: str | None):
        raw_phone = (raw_phone or "").strip()
        if not raw_phone:
            show_snackbar("Введите номер телефона")
            return

        normalized = "".join(ch for ch in raw_phone if ch.isdigit() or ch in "+*#")
        if not normalized:
            show_snackbar("Некорректный номер телефона")
            return

        show_snackbar("Открываю контакт...")
        if contact_launcher is None:
            show_snackbar("Нативный запуск контактов недоступен. Пересоберите APK.")
            return
        try:
            request_id = contact_launcher.open_contact(normalized)
            pending_contact_requests[request_id] = normalized
        except ContactLauncherError as ex:
            show_snackbar(f"Не удалось открыть контакт: {ex}")
        except Exception as ex:
            show_snackbar(f"Не удалось запустить контакт: {ex}")

    def open_contact_profile_by_phone(e=None):
        open_contact_by_phone(phone_input.value)

    def refresh_task_list():
        filtered = [t for t in tasks if (not t.get("deleted")) and t.get("date") == selected_date]
        for index, task in enumerate(filtered):
            task.setdefault("section", "day")
            if task.get("sortOrder") is None:
                task["sortOrder"] = task.get("createdAt") or index
        filtered.sort(key=lambda t: ((t.get("section") or "day"), int(t.get("sortOrder") or 0), t.get("time") or ""))

        if not filtered:
            task_list.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=60, color=ft.Colors.GREY_300),
                            ft.Text("Нет задач на этот день", size=18, color=ft.Colors.GREY_400),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    alignment=ft.Alignment(0.5, 0.5),
                    padding=40,
                )
            ]
        else:
            task_list.controls = [build_task_section(section_key, label, filtered) for section_key, label in TASK_SECTIONS]

        page.update()

    def task_items_for(date_str: str, section_key: str, items: list[dict] | None = None, exclude_id: str | None = None):
        source = items if items is not None else tasks
        section_tasks = [
            t
            for t in source
            if (not t.get("deleted"))
            and t.get("date") == date_str
            and (t.get("section") or "day") == section_key
            and t.get("id") != exclude_id
        ]
        section_tasks.sort(key=lambda t: (int(t.get("sortOrder") or 0), t.get("time") or "", t.get("createdAt") or 0))
        return section_tasks

    def section_items(section_key: str, items: list[dict] | None = None):
        return task_items_for(selected_date, section_key, items)

    def find_task(task_id: str):
        for task in tasks:
            if task.get("id") == task_id:
                return task
        return None

    def persist_section_order(section_key: str, ordered_tasks: list[dict]):
        now_ms = int(datetime.now().timestamp() * 1000)
        for index, task in enumerate(ordered_tasks):
            task["section"] = section_key
            task["sortOrder"] = index
            task["updatedAt"] = now_ms
            task["dirty"] = True
        save_tasks(tasks)

    def persist_order_for_date_section(date_str: str, section_key: str):
        now_ms = int(datetime.now().timestamp() * 1000)
        for index, task in enumerate(task_items_for(date_str, section_key)):
            task["sortOrder"] = index
            task["updatedAt"] = now_ms
            task["dirty"] = True

    def move_task_to_section(task_id: str, target_section: str, target_task_id: str | None = None):
        task = find_task(task_id)
        if not task:
            return

        old_section = task.get("section") or "day"
        task_date = task.get("date") or selected_date
        target_items = task_items_for(task_date, target_section, exclude_id=task_id)
        insert_at = len(target_items)
        if target_task_id:
            for index, item in enumerate(target_items):
                if item.get("id") == target_task_id:
                    insert_at = index
                    break

        target_items.insert(insert_at, task)
        now_ms = int(datetime.now().timestamp() * 1000)
        task["section"] = target_section
        task["updatedAt"] = now_ms
        task["dirty"] = True

        if old_section != target_section:
            persist_order_for_date_section(task_date, old_section)

        for index, item in enumerate(target_items):
            item["section"] = target_section
            item["sortOrder"] = index
            item["updatedAt"] = now_ms
            item["dirty"] = True

        save_tasks(tasks)
        refresh_task_list()

    def move_task_to_date(task_id: str, target_date: str):
        task = find_task(task_id)
        if not task:
            return

        old_date = task.get("date") or selected_date
        section_key = task.get("section") or "day"
        now_ms = int(datetime.now().timestamp() * 1000)

        task["date"] = target_date
        task["sortOrder"] = len(task_items_for(target_date, section_key, exclude_id=task_id))
        task["updatedAt"] = now_ms
        task["dirty"] = True

        if old_date != target_date:
            persist_order_for_date_section(old_date, section_key)

        save_tasks(tasks)
        refresh_task_list()
        show_snackbar("Заметка перенесена")

    def show_confirm_section_move(task_id: str, target_section: str, target_task_id: str | None = None):
        task = find_task(task_id)
        if not task:
            return

        source_label = TASK_SECTION_LABELS.get(task.get("section") or "day", "День")
        target_label = TASK_SECTION_LABELS.get(target_section, "День")

        def close_dialog(e=None):
            confirm_dialog.open = False
            page.update()

        def confirm(e=None):
            confirm_dialog.open = False
            move_task_to_section(task_id, target_section, target_task_id)

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Перенести заметку?"),
            content=ft.Text(f"Перенести из раздела «{source_label}» в «{target_label}»?"),
            actions=[
                ft.TextButton("Отмена", on_click=close_dialog),
                ft.TextButton("Перенести", on_click=confirm),
            ],
        )
        try:
            page.show_dialog(confirm_dialog)
        except Exception:
            page.dialog = confirm_dialog
            confirm_dialog.open = True
            page.update()

    def move_task_to_section_from_menu(task_id: str, target_section: str):
        task = find_task(task_id)
        if not task:
            return
        current_section = task.get("section") or "day"
        if current_section == target_section:
            show_snackbar("Заметка уже в этом разделе")
            return
        show_confirm_section_move(task_id, target_section)

    def open_move_date_dialog(task_id: str):
        task = find_task(task_id)
        if not task:
            return

        def on_destination_date(date_str: str):
            move_date_dialog.open = False
            move_task_to_date(task_id, date_str)
            page.update()

        move_calendar = CalendarComponent(on_date_select=on_destination_date)
        task_date = task.get("date") or selected_date
        try:
            parsed_date = datetime.strptime(task_date, "%Y-%m-%d").date()
            move_calendar.current_year = parsed_date.year
            move_calendar.current_month = parsed_date.month
            move_calendar.selected_date = task_date
            move_calendar._build_ui()
        except Exception:
            pass

        def close_dialog(e=None):
            move_date_dialog.open = False
            page.update()

        move_date_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Выберите день"),
            content=ft.Container(content=move_calendar, width=350),
            actions=[ft.TextButton("Отмена", on_click=close_dialog)],
        )
        try:
            page.show_dialog(move_date_dialog)
        except Exception:
            page.dialog = move_date_dialog
            move_date_dialog.open = True
            page.update()

    def build_drop_target(section_key: str, target_task_id: str | None = None, content: ft.Control | None = None):
        def on_accept(e, target_section=section_key, target_id=target_task_id):
            nonlocal dragging_task_id
            dragged = getattr(e, "src", None)
            if dragged is None and getattr(e, "src_id", None) is not None:
                dragged = page.get_control(e.src_id)
            task_id = dragging_task_id or getattr(dragged, "data", None)
            dragging_task_id = ""
            if not task_id or task_id == target_id:
                return

            task = find_task(task_id)
            if not task:
                return

            current_section = task.get("section") or "day"
            if current_section != target_section:
                show_confirm_section_move(task_id, target_section, target_id)
            else:
                move_task_to_section(task_id, target_section, target_id)

        return ft.DragTarget(
            group="tasks",
            content=content or ft.Container(
                height=22,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.BLUE),
            ),
            on_accept=on_accept,
        )

    def build_drag_handle(task: dict):
        def on_drag_start(e=None):
            nonlocal dragging_task_id
            dragging_task_id = task.get("id") or ""

        def on_drag_complete(e=None):
            nonlocal dragging_task_id
            dragging_task_id = ""

        task_text = task.get("text") or "Заметка"
        preview_text = (task_text[:42] + "...") if len(task_text) > 45 else task_text
        handle = ft.Container(
            content=ft.Icon(ft.Icons.DRAG_INDICATOR, color=ft.Colors.GREY_500),
            padding=ft.Padding(8, 8, 8, 8),
            tooltip="Перетащить",
        )
        return ft.Draggable(
            group="tasks",
            data=task.get("id"),
            content=handle,
            on_drag_start=on_drag_start,
            on_drag_complete=on_drag_complete,
            content_feedback=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DRAG_INDICATOR, color=ft.Colors.BLUE),
                        ft.Text(preview_text, size=15, weight=ft.FontWeight.W_600),
                    ],
                    spacing=8,
                ),
                width=320,
                bgcolor=ft.Colors.WHITE,
                border_radius=14,
                padding=ft.Padding(12, 10, 12, 10),
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK)),
            ),
        )

    def estimate_task_height(task: dict) -> int:
        height = 122
        text_len = len(task.get("text") or "")
        if text_len > 34:
            height += min(6, (text_len - 1) // 34) * 24
        if task.get("address"):
            height += 50
        if task.get("phone"):
            height += 50
        if task.get("lat") is not None and task.get("lon") is not None:
            height += 285
        return height

    def build_draggable_task(task: dict):
        task_text = task.get("text") or "Заметка"
        preview_text = (task_text[:42] + "...") if len(task_text) > 45 else task_text
        return ft.Draggable(
            group="tasks",
            data=task.get("id"),
            content=build_task_item(task, drag_handle=build_drag_handle(task)),
            content_when_dragging=ft.Container(
                content=build_task_item(task, drag_handle=build_drag_handle(task)),
                opacity=0.35,
            ),
            content_feedback=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.DRAG_INDICATOR, color=ft.Colors.BLUE),
                        ft.Text(preview_text, size=15, weight=ft.FontWeight.W_600),
                    ],
                    spacing=8,
                ),
                width=280,
                bgcolor=ft.Colors.WHITE,
                border_radius=14,
                padding=ft.Padding(12, 10, 12, 10),
                shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.22, ft.Colors.BLACK)),
            ),
        )

    def build_task_section(section_key: str, label: str, filtered: list[dict]):
        items = section_items(section_key, filtered)

        if not items:
            content = build_drop_target(
                section_key,
                content=ft.Container(
                    content=ft.Text("Нет заметок", color=ft.Colors.GREY_400, size=14),
                    padding=ft.Padding(12, 8, 12, 8),
                    border_radius=8,
                ),
            )
        else:
            controls = [
                build_drop_target(
                    section_key,
                    target_task_id=task.get("id"),
                    content=build_task_item(
                        task,
                        drag_handle=build_drag_handle(task),
                    )
                )
                for task in items
            ]
            controls.append(build_drop_target(section_key))
            content = ft.Column(controls=controls, spacing=0)

        return ft.Column(
            controls=[
                ft.Text(label, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_700),
                content,
            ],
            spacing=8,
        )

    def build_task_item(task, drag_handle=None):
        is_completed = bool(task.get("completed"))
        map_url = task.get("mapUrl")
        lat = task.get("lat")
        lon = task.get("lon")
        task_phone = (task.get("phone") or "").strip()

        task_menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            tooltip="Действия",
            items=[
                ft.PopupMenuItem(
                    content=ft.Text("Перенести на день"),
                    icon=ft.Icons.EVENT,
                    data="move_day",
                    on_click=lambda e, tid=task["id"]: open_move_date_dialog(tid),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("В раздел: Утро"),
                    icon=ft.Icons.WB_SUNNY_OUTLINED,
                    data="section:morning",
                    on_click=lambda e, tid=task["id"]: move_task_to_section_from_menu(tid, "morning"),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("В раздел: День"),
                    icon=ft.Icons.WB_SUNNY,
                    data="section:day",
                    on_click=lambda e, tid=task["id"]: move_task_to_section_from_menu(tid, "day"),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("В раздел: Вечер"),
                    icon=ft.Icons.NIGHTS_STAY_OUTLINED,
                    data="section:evening",
                    on_click=lambda e, tid=task["id"]: move_task_to_section_from_menu(tid, "evening"),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Удалить"),
                    icon=ft.Icons.DELETE_OUTLINE,
                    data="delete",
                    on_click=lambda e, tid=task["id"]: delete_task(tid),
                ),
            ],
        )

        map_controls: list[ft.Control] = []
        if lat is not None and lon is not None:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except Exception:
                lat_f = None
                lon_f = None

            if lat_f is not None and lon_f is not None:
                map_size = 220
                current_lat = lat_f
                current_lon = lon_f

                img = ft.Image(
                    src=_static_osm_map_url(current_lat, current_lon, width=map_size, height=map_size),
                    width=map_size,
                    height=map_size,
                    fit=ft.ImageFit.CONTAIN if hasattr(ft, "ImageFit") else "contain",
                )

                def on_map_tap(e=None):
                    show_snackbar("Открываю карту...")
                    open_map_image(_static_osm_map_url(current_lat, current_lon, width=650, height=450))

                clickable = ft.Container(
                    content=img,
                    on_click=on_map_tap,
                    ink=True,
                    border_radius=12,
                )

                tappable = clickable

                def update_map(new_lat, new_lon):
                    nonlocal current_lat, current_lon
                    try:
                        current_lat = float(new_lat)
                        current_lon = float(new_lon)
                        img.src = _static_osm_map_url(current_lat, current_lon, width=map_size, height=map_size)
                        img.update()
                    except Exception:
                        pass

                update_map(lat_f, lon_f)
                map_controls.append(tappable)
                map_controls.append(
                    ft.TextButton(
                        "Увеличить карту",
                        on_click=on_map_tap,
                    )
                )

        return ft.Container(
            key=task.get("id"),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=ft.Text(
                                            task.get("time", ""),
                                            size=15,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.BLUE,
                                        ),
                                        bgcolor=ft.Colors.GREY_100,
                                        padding=ft.Padding(12, 6, 12, 6),
                                        border_radius=8,
                                        visible=bool(task.get("time")),
                                    ),
                                    ft.Container(
                                        content=ft.Text(
                                            (task.get("date", "0000-00-00")[8:10] + "." + task.get("date", "0000-00-00")[5:7]),
                                            size=15,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.GREEN_700,
                                        ),
                                        bgcolor=ft.Colors.GREEN_50,
                                        padding=ft.Padding(12, 6, 12, 6),
                                        border_radius=8,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                controls=[
                                    ft.IconButton(
                                        icon=ft.Icons.CHECK_CIRCLE if is_completed else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                        icon_color=ft.Colors.GREEN if is_completed else ft.Colors.GREY_400,
                                        on_click=lambda e, tid=task["id"]: toggle_task(tid),
                                    ),
                                    task_menu,
                                    drag_handle or ft.Container(width=40),
                                ],
                                spacing=0,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        task.get("text", ""),
                        size=17,
                        color=ft.Colors.GREY_500 if is_completed else ft.Colors.BLACK,
                    ),
                    ft.TextButton(
                        task.get("address", ""),
                        visible=bool(map_url),
                        on_click=lambda e, u=map_url: open_url(u),
                    ),
                    ft.TextButton(
                        f"Контакт: {task_phone}",
                        visible=bool(task_phone),
                        on_click=lambda e, p=task_phone: open_contact_by_phone(p),
                    ),
                    *map_controls,
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.WHITE,
            border_radius=16,
            padding=16,
            margin=ft.Margin(0, 0, 0, 10),
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK)),
            opacity=0.85 if is_completed else 1.0,
        )

    def add_task(e=None):
        nonlocal selected_time, tasks

        if not user_id:
            show_snackbar("Нужно войти в аккаунт")
            return

        text = (task_input.value or "").strip()
        if not text:
            show_snackbar("Заполните задачу")
            return

        parsed = parse_datetime_from_text(text)
        final_time = selected_time or parsed.get("time") or ""
        final_date = parsed.get("date") if parsed.get("has_date") else selected_date

        if False and not final_time:
            show_snackbar("Укажите время в тексте или выберите вручную")
            return

        now_ms = int(datetime.now().timestamp() * 1000)
        task_section = section_dropdown.value or selected_section or "day"
        next_order = len(
            [
                t
                for t in tasks
                if (not t.get("deleted"))
                and t.get("date") == final_date
                and (t.get("section") or "day") == task_section
            ]
        )

        address_value = (address_input.value or "").strip()
        phone_value = (phone_input.value or "").strip()
        lat = None
        lon = None
        map_url = None

        if address_value:
            try:
                city_bias = (os.getenv("NOMINATIM_CITY") or "").strip()
                query = f"{city_bias}, {address_value}" if city_bias else address_value
                q = quote_plus(query)
                url = f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1&addressdetails=1"
                req = Request(
                    url,
                    headers={
                        "User-Agent": "DiaryFlet/1.0",
                        "Accept": "application/json",
                    },
                    method="GET",
                )
                with urlopen(req, timeout=10) as resp:
                    payload = resp.read().decode("utf-8")
                data = json.loads(payload) or []
                if data:
                    lat = float(data[0].get("lat")) if data[0].get("lat") is not None else None
                    lon = float(data[0].get("lon")) if data[0].get("lon") is not None else None

                if lat is not None and lon is not None:
                    map_url = f"https://yandex.ru/maps/?pt={lon},{lat}&z=16&l=map"
                else:
                    show_snackbar("Адрес не найден (Nominatim)")
            except Exception as ex:
                show_snackbar(f"Ошибка геокодинга: {ex}")

        new_task = {
            "id": str(now_ms),
            "userId": user_id,
            "text": text,
            "address": address_value or None,
            "phone": phone_value or None,
            "section": task_section,
            "sortOrder": next_order,
            "lat": lat,
            "lon": lon,
            "mapUrl": map_url,
            "time": final_time,
            "date": final_date,
            "completed": False,
            "deleted": False,
            "dirty": True,
            "createdAt": now_ms,
            "updatedAt": now_ms,
        }

        tasks.insert(0, new_task)
        save_tasks(tasks)

        task_input.value = ""
        address_input.value = ""
        phone_input.value = ""
        selected_time = ""
        time_display.content = ft.Text("Время", color=ft.Colors.GREY_400, size=16)

        refresh_task_list()

    def toggle_task(task_id: str):
        nonlocal tasks
        for t in tasks:
            if t.get("id") == task_id:
                t["completed"] = not bool(t.get("completed"))
                t["updatedAt"] = int(datetime.now().timestamp() * 1000)
                t["dirty"] = True
                break
        save_tasks(tasks)
        refresh_task_list()

    def delete_task(task_id: str):
        nonlocal tasks
        for t in tasks:
            if t.get("id") == task_id:
                t["deleted"] = True
                t["updatedAt"] = int(datetime.now().timestamp() * 1000)
                t["dirty"] = True
                break
        save_tasks(tasks)
        refresh_task_list()

    def apply_task_datetime_from_text(text: str):
        nonlocal selected_time
        parsed = parse_datetime_from_text(text)
        if parsed.get("has_time"):
            selected_time = parsed.get("time")
            time_display.content = ft.Text(selected_time, color=ft.Colors.BLACK, size=16, weight=ft.FontWeight.BOLD)
            page.update()
        if parsed.get("has_date"):
            on_calendar_date_select(parsed.get("date"))

    def on_task_text_change(e):
        apply_task_datetime_from_text(e.control.value or "")

    def on_time_selected(time_str: str):
        nonlocal selected_time
        selected_time = time_str
        time_display.content = ft.Text(time_str, color=ft.Colors.BLACK, size=16, weight=ft.FontWeight.BOLD)
        page.update()

    def on_calendar_date_select(date_str: str):
        nonlocal selected_date
        selected_date = date_str
        date_display.content = ft.Text(format_date_display(date_str), color=ft.Colors.BLUE, size=16, weight=ft.FontWeight.BOLD)
        calendar_component.selected_date = date_str
        refresh_task_list()
        calendar_dialog.open = False
        page.update()

    def open_time_picker():
        create_time_picker(page, selected_time, on_time_selected)

    def open_calendar():
        page.dialog = calendar_dialog
        calendar_dialog.open = True
        page.update()

    def do_sync(e=None):
        nonlocal tasks
        if not access_token or not user_id:
            show_snackbar("Войдите в аккаунт для синхронизации")
            return
        try:
            tasks = sync_once(access_token=access_token, user_id=user_id)
            refresh_task_list()
            show_snackbar("Синхронизация завершена")
        except Exception as ex:
            show_snackbar(f"Ошибка синхронизации: {ex}")

    def update_voice_buttons():
        buttons = (task_mic_button, address_mic_button)
        for button in buttons:
            if not stt_available:
                button.icon = ft.Icons.MIC_OFF
                button.icon_color = ft.Colors.GREY_400
                button.tooltip = "Голосовой ввод недоступен"
                button.disabled = True
                try:
                    button.update()
                except Exception:
                    pass
                continue

            active = voice_listening and button == voice_button
            button.icon = ft.Icons.MIC if active else ft.Icons.MIC_NONE
            button.icon_color = ft.Colors.RED_500 if active else ft.Colors.BLUE
            button.tooltip = "Остановить голосовой ввод" if active else "Голосовой ввод"
            button.disabled = False
            try:
                button.update()
            except Exception:
                pass

    def apply_voice_text(text: str):
        if not voice_target:
            return
        recognized = (text or "").strip()
        if not recognized:
            return

        base = voice_base_text.strip()
        voice_target.value = f"{base} {recognized}".strip() if base else recognized
        if voice_target == task_input:
            apply_task_datetime_from_text(voice_target.value or "")
        try:
            voice_target.update()
        except Exception:
            page.update()

    def on_stt_result(e):
        try:
            result = SttResult(e)
        except Exception:
            return
        apply_voice_text(result.text)

    def on_stt_error(e):
        nonlocal voice_listening
        voice_listening = False
        update_voice_buttons()
        try:
            error = SttErrorData(e)
            show_snackbar(f"Ошибка распознавания: {error.error}")
        except Exception:
            show_snackbar("Ошибка распознавания речи")

    def on_stt_status(e):
        nonlocal voice_listening
        try:
            status = SttStatus(e)
        except Exception:
            return
        voice_listening = status.listening
        update_voice_buttons()

    async def resolve_stt_locale() -> str:
        if not stt:
            return ""
        try:
            locales = await stt.locales()
        except Exception:
            locales = []

        locale_ids = {str(item.get("id", "")) for item in locales if isinstance(item, dict)}
        for candidate in ("ru_RU", "ru-RU", "ru"):
            if candidate in locale_ids:
                return candidate

        for loc in locale_ids:
            if loc.lower().startswith("ru"):
                return loc

        try:
            system_loc = await stt.system_locale()
            system_id = str(system_loc.get("id", "")).strip() if isinstance(system_loc, dict) else ""
            if system_id:
                return system_id
        except Exception:
            pass

        return ""

    async def toggle_voice_input(target: ft.TextField, button: ft.IconButton):
        nonlocal stt_initialized, voice_base_text, voice_button, voice_listening, voice_target, selected_stt_locale

        try:
            if not stt_available or stt is None:
                show_snackbar("Установите пакет flet-stt для голосового ввода")
                return

            voice_target = target
            voice_button = button

            if voice_listening:
                await stt.stop()
                voice_listening = False
                update_voice_buttons()
                return

            voice_base_text = target.value or ""

            if not stt_initialized:
                stt_initialized = await stt.initialize()
                if stt_initialized:
                    selected_stt_locale = await resolve_stt_locale()

            if not stt_initialized:
                show_snackbar("Голосовой ввод недоступен на этом устройстве")
                return

            voice_listening = True
            update_voice_buttons()
            show_snackbar("Говорите...")
            await stt.listen(
                locale_id=selected_stt_locale,
                listen_for_seconds=45,
                pause_for_seconds=3,
                partial_results=True,
                listen_mode="dictation",
                cancel_on_error=True,
                cloud_timeout_seconds=20,
            )
        except SttError as ex:
            voice_listening = False
            update_voice_buttons()
            show_snackbar(f"Не удалось запустить голосовой ввод: {ex}")
        except Exception as ex:
            voice_listening = False
            update_voice_buttons()
            show_snackbar(f"Ошибка голосового ввода: {ex}")

    # UI controls
    task_input = ft.TextField(
        hint_text="Что нужно сделать?",
        expand=True,
        border_radius=12,
        filled=True,
        bgcolor=ft.Colors.WHITE,
        on_change=on_task_text_change,
    )

    address_input = ft.TextField(
        hint_text="Адрес (необязательно)",
        expand=True,
        border_radius=12,
        filled=True,
        bgcolor=ft.Colors.WHITE,
    )

    phone_input = ft.TextField(
        hint_text="Телефон контакта",
        expand=True,
        border_radius=12,
        filled=True,
        bgcolor=ft.Colors.WHITE,
        keyboard_type=ft.KeyboardType.PHONE,
    )

    open_contact_button = ft.IconButton(
        icon=ft.Icons.CONTACT_PHONE,
        icon_color=ft.Colors.BLUE,
        tooltip="Открыть контакт в телефонной книге",
        on_click=open_contact_profile_by_phone,
    )

    def on_task_mic_click(e):
        page.run_task(toggle_voice_input, task_input, task_mic_button)

    def on_address_mic_click(e):
        page.run_task(toggle_voice_input, address_input, address_mic_button)

    task_mic_button = ft.IconButton(
        icon=ft.Icons.MIC_NONE,
        icon_color=ft.Colors.BLUE,
        tooltip="Голосовой ввод заметки",
        on_click=on_task_mic_click,
        disabled=not stt_available,
    )

    address_mic_button = ft.IconButton(
        icon=ft.Icons.MIC_NONE,
        icon_color=ft.Colors.BLUE,
        tooltip="Голосовой ввод адреса",
        on_click=on_address_mic_click,
        disabled=not stt_available,
    )

    if stt is not None:
        stt.on_result = on_stt_result
        stt.on_error = on_stt_error
        stt.on_status = on_stt_status

    def on_section_change(e):
        nonlocal selected_section
        selected_section = section_dropdown.value or "day"

    section_dropdown = ft.Dropdown(
        value=selected_section,
        options=[
            ft.DropdownOption(key=key, text=label)
            for key, label in TASK_SECTIONS
        ],
        on_select=on_section_change,
        width=130,
        border_radius=12,
        filled=True,
        bgcolor=ft.Colors.WHITE,
    )

    time_display = ft.Container(
        content=ft.Text("Время", color=ft.Colors.GREY_400, size=16),
        padding=ft.Padding(16, 14, 16, 14),
        border_radius=12,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.BLUE),
        on_click=lambda e: open_time_picker(),
        width=90,
    )

    date_display = ft.Container(
        content=ft.Text(format_date_display(selected_date), color=ft.Colors.BLUE, size=16, weight=ft.FontWeight.BOLD),
        padding=ft.Padding(16, 14, 16, 14),
        border_radius=12,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.BLUE),
        on_click=lambda e: open_calendar(),
        width=80,
    )

    calendar_component = CalendarComponent(on_date_select=on_calendar_date_select)
    calendar_dialog = ft.AlertDialog(
        modal=True,
        content=ft.Container(content=calendar_component, width=350),
        actions=[ft.TextButton("Отмена", on_click=lambda e: open_calendar())],
    )

    def open_auth_view():
        root_controls().clear()

        email = ft.TextField(label="Email", width=320)
        password = ft.TextField(label="Пароль", width=320, password=True, can_reveal_password=True)

        def on_login(e=None):
            nonlocal access_token, user_id, tasks
            try:
                show_snackbar("Выполняю вход...")
                res = sign_in_with_password(email.value.strip(), password.value)
                sess = res.get("session") or {}
                access_token = sess.get("access_token")
                user = res.get("user") or {}
                user_id = user.get("id")
                if not access_token or not user_id:
                    raise RuntimeError("Не удалось получить access_token/user_id")

                save_session({"access_token": access_token, "user_id": user_id})

                tasks = sync_once(access_token=access_token, user_id=user_id)
                open_app_view()
            except Exception as ex:
                show_snackbar(f"Ошибка входа: {ex}")

        def on_register(e=None):
            try:
                show_snackbar("Регистрирую...")
                sign_up(email.value.strip(), password.value)
                show_snackbar("Аккаунт создан. Теперь войдите.")
            except Exception as ex:
                show_snackbar(f"Ошибка регистрации: {ex}")

        root_controls().extend(
            [
            ft.Text("Вход", size=28, weight=ft.FontWeight.BOLD),
            email,
            password,
            ft.Row(
                controls=[
                    ft.Button("Войти", on_click=on_login),
                    ft.OutlinedButton("Регистрация", on_click=on_register),
                ],
                spacing=12,
            ),
            ]
        )

        page.update()

    def open_app_view():
        root_controls().clear()

        def on_logout(e=None):
            nonlocal access_token, user_id, tasks
            access_token = None
            user_id = None
            tasks = load_tasks()
            clear_session()
            open_auth_view()

        root_controls().extend(
            [
            ft.Row(
                controls=[
                    ft.Text("Мои задачи", size=28, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(icon=ft.Icons.SYNC, on_click=do_sync),
                    ft.IconButton(icon=ft.Icons.LOGOUT, on_click=on_logout),
                ]
            ),
            ft.Container(
                content=calendar_component,
                bgcolor=ft.Colors.WHITE,
                border_radius=16,
                padding=16,
                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK)),
            ),
            ft.Row(
                controls=[ft.Text(format_date_full(selected_date), size=18, weight=ft.FontWeight.W_600, expand=True)],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[task_input, task_mic_button],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[address_input, address_mic_button],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[phone_input, open_contact_button],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[
                            section_dropdown,
                            time_display,
                            date_display,
                            ft.Container(
                                content=ft.Icon(ft.Icons.ADD, color=ft.Colors.WHITE, size=28),
                                bgcolor=ft.Colors.BLUE,
                                border_radius=16,
                                width=56,
                                height=56,
                                alignment=ft.Alignment(0.5, 0.5),
                                on_click=add_task,
                                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.3, ft.Colors.BLUE)),
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
            task_list,
            ]
        )
        refresh_task_list()
        page.update()

    if access_token and user_id:
        try:
            tasks = sync_once(access_token=access_token, user_id=user_id)
        except Exception:
            clear_session()
            access_token = None
            user_id = None
            open_auth_view()
        else:
            open_app_view()
    else:
        open_auth_view()


if __name__ == "__main__":
    ft.run(main)
