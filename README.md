# Diary (Flet)

Простое приложение задач на Python + Flet.

## Возможности

- Задачи по датам (календарь)
- Выбор времени (шаг 10 минут)
- Авто-извлечение даты/времени из текста заметки
- Локальное хранение задач в SQLite (`tasks.db`)

## Установка

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск (Desktop)

```bash
python main.py
```

## Сборка APK (Android)

Требуется установленный Flutter и Android SDK.

```bash
flutter doctor --android-licenses
flet build apk
```

Готовый APK:

- `build/flutter/build/app/outputs/apk/release/app-release.apk`

## Примечания

- `tasks.db` создаётся в директории приложения (на Android — в app storage)