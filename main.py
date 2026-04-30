import flet as ft
from datetime import date, datetime

from components.calendar import CalendarComponent
from components.time_picker import create_time_picker
from utils.storage import load_tasks, save_tasks
from utils.date_parser import parse_datetime_from_text


def format_date_display(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d')
    return d.strftime('%d.%m')


def format_date_full(date_str):
    d = datetime.strptime(date_str, '%Y-%m-%d')
    months = [
        '', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ]
    weekdays = [
        'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'
    ]
    return f'{weekdays[d.weekday()]}, {d.day} {months[d.month]} {d.year}'


def main(page: ft.Page):
    page.title = 'Мои задачи'
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 30
    page.scroll = ft.ScrollMode.AUTO

    # Состояние приложения
    selected_date = date.today().strftime('%Y-%m-%d')
    selected_time = ''
    tasks = load_tasks()

    # Список задач
    task_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    #  Функции (определены ДО UI элементов) 

    def refresh_task_list():
        filtered = [t for t in tasks if t['date'] == selected_date]
        filtered.sort(key=lambda t: t['time'])

        if not filtered:
            task_list.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=60, color=ft.Colors.GREY_300),
                            ft.Text('Нет задач на этот день', size=18, color=ft.Colors.GREY_400),
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
        is_completed = task['completed']
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(task['time'], size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE),
                        bgcolor=ft.Colors.GREY_100,
                        padding=ft.Padding(12, 6, 12, 6),
                        border_radius=8,
                    ),
                    ft.Container(
                        content=ft.Text(task['date'][8:10] + '.' + task['date'][5:7], size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                        bgcolor=ft.Colors.GREEN_50,
                        padding=ft.Padding(12, 6, 12, 6),
                        border_radius=8,
                    ),
                    ft.Text(
                        task['text'],
                        size=17,
                        color=ft.Colors.GREY_500 if is_completed else ft.Colors.BLACK,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE if is_completed else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        icon_color=ft.Colors.GREEN if is_completed else ft.Colors.GREY_400,
                        on_click=lambda e, tid=task['id']: toggle_task(tid),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda e, tid=task['id']: delete_task(tid),
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
        nonlocal selected_time
        text = task_input.value.strip()
        if not text:
            show_snackbar('Заполните задачу')
            return

        parsed = parse_datetime_from_text(text)
        final_time = selected_time or parsed['time']
        final_date = parsed['date'] if parsed['has_date'] else selected_date

        if not final_time:
            show_snackbar('Укажите время в тексте или выберите вручную')
            return

        new_task = {
            'id': str(int(datetime.now().timestamp() * 1000)),
            'text': text,
            'time': final_time,
            'date': final_date,
            'completed': False,
        }

        tasks.insert(0, new_task)
        save_tasks(tasks)

        task_input.value = ''
        selected_time = ''
        time_display.content = ft.Text('18:30', color=ft.Colors.GREY_400, size=16)
        refresh_task_list()

    def toggle_task(task_id):
        for task in tasks:
            if task['id'] == task_id:
                task['completed'] = not task['completed']
                break
        save_tasks(tasks)
        refresh_task_list()

    def delete_task(task_id):
        nonlocal tasks
        tasks = [t for t in tasks if t['id'] != task_id]
        save_tasks(tasks)
        refresh_task_list()

    def on_task_text_change(e):
        nonlocal selected_time
        text = e.control.value
        parsed = parse_datetime_from_text(text)
        if parsed['has_time']:
            selected_time = parsed['time']
            time_display.content = ft.Text(selected_time, color=ft.Colors.BLACK, size=16, weight=ft.FontWeight.BOLD)
            page.update()
        if parsed['has_date']:
            on_calendar_date_select(parsed['date'])

    def on_time_selected(time):
        nonlocal selected_time
        selected_time = time
        time_display.content = ft.Text(time, color=ft.Colors.BLACK, size=16, weight=ft.FontWeight.BOLD)
        page.update()

    def on_calendar_date_select(date_str):
        nonlocal selected_date
        selected_date = date_str
        date_display.content = ft.Text(format_date_display(date_str), color=ft.Colors.BLUE, size=16, weight=ft.FontWeight.BOLD)
        calendar_component.selected_date = date_str
        refresh_task_list()
        close_dialog(calendar_dialog)

    def open_time_picker():
        create_time_picker(page, selected_time, on_time_selected)

    def open_calendar():
        page.show_dialog(calendar_dialog)

    def close_dialog(dialog):
        page.pop_dialog()

    def show_snackbar(msg):
        page.overlay.append(ft.SnackBar(content=ft.Text(msg)))
        page.update()

    #  UI элементы (после функций) 

    task_input = ft.TextField(
        hint_text='Что нужно сделать?',
        expand=True,
        border_radius=12,
        filled=True,
        bgcolor=ft.Colors.WHITE,
        on_change=on_task_text_change,
    )

    time_display = ft.Container(
        content=ft.Text('18:30', color=ft.Colors.GREY_400, size=16),
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

    # Календарь
    calendar_component = CalendarComponent(on_date_select=on_calendar_date_select)
    calendar_dialog = ft.AlertDialog(
        modal=True,
        content=ft.Container(
            content=calendar_component,
            width=350,
        ),
        actions=[
            ft.TextButton('Отмена', on_click=lambda e: close_dialog(calendar_dialog)),
        ],
    )

    #  Собираем интерфейс 
    page.add(
        ft.Text('Мои задачи', size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
        ft.Container(
            content=calendar_component,
            bgcolor=ft.Colors.WHITE,
            border_radius=16,
            padding=16,
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK)),
        ),
        ft.Row(
            controls=[
                ft.Text(format_date_full(selected_date), size=18, weight=ft.FontWeight.W_600, expand=True),
            ],
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


if __name__ == '__main__':
    ft.run(main)
