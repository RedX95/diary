import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'tasks.json')


def load_tasks():
    """Загрузить задачи из файла"""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_tasks(tasks):
    """Сохранить задачи в файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
