#!/usr/bin/env python3
import os
import sys

from sqlalchemy.orm import sessionmaker


def setup_project():
    print("[INIT] Настройка проекта...")

    # 1. Создаем папки
    for folder in ["config", "database", "logs"]:
        os.makedirs(folder, exist_ok=True)
        print(f"  ✅ Папка /{folder} готова")

    # 2. Создаем config/settings.py, если нет
    settings_path = os.path.join("app/config", "settings.py")
    if not os.path.exists(settings_path):
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write("""DEBUG = bool(os.getenv('DEBUG'))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.getenv("DATABASE_URL")
LOG_DIR = os.path.join(BASE_DIR, "logs")
INTERFACE_NAME = "awg0"
MIRROR_INTERFACE_NAME = "ifb0"
SPEED_CEIL = 600
SUBNET_PREFIX = "10.10.10."
SERVER_PUBLIC_KEY = ""
SERVER_ENDPOINT = "111.222.233.244:55667"
SERVER_CONFIG_DATA = "\n## Тут можно вставить Jc, Jmax...\n"
""")
        print("  ✅ config/settings.py создан")
    else:
        print("  ⚠️ config/settings.py уже существует")

    # 3. Инициализируем БД
    from app.database import Base, engine
    if not os.path.exists("data/vpn.db"):
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        print("  ✅ База данных создана")
    else:
        print("  ⚠️ База данных уже существует")


    print("[INIT] Готово. Можешь запускать проект.")
    input("Нажми Enter для выхода...")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    setup_project()