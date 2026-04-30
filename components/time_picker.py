import flet as ft


def generate_time_slots():
    times = []
    for hour in range(24):
        for minute in range(0, 60, 10):
            times.append(f'{hour:02d}:{minute:02d}')
    return times


TIME_SLOTS = generate_time_slots()


def create_time_picker(page, selected_time, on_time_select):
    """Создать и показать диалог выбора времени"""

    def _close_dlg(p):
        p.pop_dialog()

    def on_time_click(e, time):
        on_time_select(time)
        _close_dlg(page)

    time_items = []
    for t in TIME_SLOTS:
        is_selected = t == selected_time
        time_items.append(
            ft.Container(
                content=ft.Text(
                    t,
                    size=18,
                    color=ft.Colors.BLUE if is_selected else ft.Colors.BLACK,
                    weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL,
                ),
                padding=ft.Padding(20, 12, 20, 12),
                border_radius=12,
                bgcolor=ft.Colors.BLUE_50 if is_selected else None,
                on_click=lambda e, time=t: on_time_click(e, time),
            )
        )

    time_dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text('Выберите время', size=20, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                controls=time_items,
                scroll=ft.ScrollMode.AUTO,
                height=400,
                width=300,
            ),
        ),
        actions=[
            ft.TextButton('Отмена', on_click=lambda e: _close_dlg(page)),
        ],
    )

    page.show_dialog(time_dlg)
