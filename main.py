import os
import json
import asyncio
from datetime import date, datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import flet as ft
try:
    from flet_stt import FletStt, SttError, SttErrorData, SttResult, SttStatus
except ImportError:
    FletStt = None

    class SttError(Exception):
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
    stt_available = stt is not None
    stt_initialized = False
    selected_stt_locale = ""
    voice_target: ft.TextField | None = None
    voice_base_text = ""
    voice_button: ft.IconButton | None = None
    voice_listening = False

    def show_snackbar(msg: str):
        sb = ft.SnackBar(content=ft.Text(msg))
        page.overlay.append(sb)
        sb.open = True
        page.update()

    if stt is not None:
        page.services.append(stt)

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

    def refresh_task_list():
        filtered = [t for t in tasks if (not t.get("deleted")) and t.get("date") == selected_date]
        filtered.sort(key=lambda t: t.get("time") or "")

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
            task_list.controls = [build_task_item(task) for task in filtered]

        page.update()

    def build_task_item(task):
        is_completed = bool(task.get("completed"))
        map_url = task.get("mapUrl")
        lat = task.get("lat")
        lon = task.get("lon")

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
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=ft.Colors.RED_400,
                                        on_click=lambda e, tid=task["id"]: delete_task(tid),
                                    ),
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
                    *map_controls,
                ],
                spacing=10,
            ),
            bgcolor=ft.Colors.WHITE,
            border_radius=16,
            padding=16,
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
        final_time = selected_time or parsed.get("time")
        final_date = parsed.get("date") if parsed.get("has_date") else selected_date

        if not final_time:
            show_snackbar("Укажите время в тексте или выберите вручную")
            return

        now_ms = int(datetime.now().timestamp() * 1000)

        address_value = (address_input.value or "").strip()
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
        selected_time = ""
        time_display.content = ft.Text("18:30", color=ft.Colors.GREY_400, size=16)

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

    time_display = ft.Container(
        content=ft.Text("18:30", color=ft.Colors.GREY_400, size=16),
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
                        controls=[
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
