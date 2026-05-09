import os
from datetime import date, datetime

import flet as ft

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


async def main(page: ft.Page):
    page.title = "Мои задачи"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 30
    page.scroll = ft.ScrollMode.AUTO

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

    task_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def show_snackbar(msg: str):
        sb = ft.SnackBar(content=ft.Text(msg))
        page.overlay.append(sb)
        sb.open = True
        page.update()

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
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(task.get("time", ""), size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
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
                    ft.Text(
                        task.get("text", ""),
                        size=17,
                        color=ft.Colors.GREY_500 if is_completed else ft.Colors.BLACK,
                        expand=True,
                    ),
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
                alignment=ft.MainAxisAlignment.START,
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
        new_task = {
            "id": str(now_ms),
            "userId": user_id,
            "text": text,
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

    def on_task_text_change(e):
        nonlocal selected_time
        text = e.control.value
        parsed = parse_datetime_from_text(text)
        if parsed.get("has_time"):
            selected_time = parsed.get("time")
            time_display.content = ft.Text(selected_time, color=ft.Colors.BLACK, size=16, weight=ft.FontWeight.BOLD)
            page.update()
        if parsed.get("has_date"):
            on_calendar_date_select(parsed.get("date"))

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

    # UI controls
    task_input = ft.TextField(
        hint_text="Что нужно сделать?",
        expand=True,
        border_radius=12,
        filled=True,
        bgcolor=ft.Colors.WHITE,
        on_change=on_task_text_change,
    )

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
        page.controls.clear()

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

        page.add(
            ft.Text("Вход", size=28, weight=ft.FontWeight.BOLD),
            email,
            password,
            ft.Row(
                controls=[
                    ft.ElevatedButton("Войти", on_click=on_login),
                    ft.OutlinedButton("Регистрация", on_click=on_register),
                ],
                spacing=12,
            ),
            ft.Text(
                "Нужно указать переменные окружения: SUPABASE_URL и SUPABASE_ANON_KEY",
                size=12,
                color=ft.Colors.GREY_600,
            ),
        )

        page.update()

    def open_app_view():
        page.controls.clear()

        def on_logout(e=None):
            nonlocal access_token, user_id, tasks
            access_token = None
            user_id = None
            tasks = load_tasks()
            clear_session()
            open_auth_view()

        page.add(
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
            ft.Row(
                controls=[
                    task_input,
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
            task_list,
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
