import calendar
import flet as ft
from datetime import date, datetime


MONTH_NAMES = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
]
DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


class CalendarComponent(ft.Column):
    """Компонент календаря для выбора даты"""

    def __init__(self, on_date_select=None):
        super().__init__()
        self.on_date_select = on_date_select
        self.current_year = date.today().year
        self.current_month = date.today().month
        self.selected_date = date.today().strftime('%Y-%m-%d')
        self.spacing = 0
        self._build_ui()

    def _build_ui(self):
        self.controls = [
            self._build_header(),
            self._build_week_header(),
            self._build_days_grid(),
        ]

    def _build_header(self):
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT,
                    on_click=self._prev_month,
                    icon_color=ft.Colors.BLUE,
                ),
                ft.Text(
                    f'{MONTH_NAMES[self.current_month - 1]} {self.current_year}',
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_RIGHT,
                    on_click=self._next_month,
                    icon_color=ft.Colors.BLUE,
                ),
            ],
        )

    def _build_week_header(self):
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text(day, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600),
                    alignment=ft.Alignment(0.5, 0.5),
                    expand=True,
                )
                for day in DAY_NAMES
            ],
        )

    def _build_days_grid(self):
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)
        today = date.today()

        rows = []
        for week in month_days:
            row_controls = []
            for day_num in week:
                if day_num == 0:
                    row_controls.append(
                        ft.Container(expand=True, height=40)
                    )
                else:
                    d = date(self.current_year, self.current_month, day_num)
                    date_str = d.strftime('%Y-%m-%d')
                    is_today = d == today
                    is_selected = date_str == self.selected_date

                    bg_color = None
                    text_color = ft.Colors.BLACK
                    if is_selected:
                        bg_color = ft.Colors.BLUE
                        text_color = ft.Colors.WHITE
                    elif is_today:
                        bg_color = ft.Colors.BLUE_50
                        text_color = ft.Colors.BLUE

                    row_controls.append(
                        ft.Container(
                            content=ft.Text(
                                str(day_num),
                                size=16,
                                color=text_color,
                                weight=ft.FontWeight.BOLD if is_selected or is_today else ft.FontWeight.NORMAL,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            alignment=ft.Alignment(0.5, 0.5),
                            bgcolor=bg_color,
                            border_radius=8,
                            height=40,
                            expand=True,
                            on_click=lambda e, ds=date_str: self._on_day_click(ds),
                        )
                    )
            rows.append(ft.Row(controls=row_controls, spacing=2))

        return ft.Column(controls=rows, spacing=2)

    def _on_day_click(self, date_str):
        self.selected_date = date_str
        self._build_ui()
        self.update()
        if self.on_date_select:
            self.on_date_select(date_str)

    def _prev_month(self, e=None):
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self._build_ui()
        self.update()

    def _next_month(self, e=None):
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self._build_ui()
        self.update()
