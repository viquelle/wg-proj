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
            f.write("""import os
DEBUG = False
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "database.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
INTERFACE_NAME = "wg0"
MIRROR_INTERFACE_NAME = "ifb0"
SPEED_CEIL = 600
SUBNET_PREFIX = "10.0.0."
SERVER_IP = 127.0.0.1 ## измените это на IP вашего сервера
""")
        print("  ✅ config/settings.py создан")
    else:
        print("  ⚠️ config/settings.py уже существует")

    # 3. Инициализируем БД
    from app.database import Base, engine
    if not os.path.exists("data/vpn.db"):
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        print("  ✅ База данных создана")
    else:
        print("  ⚠️ База данных уже существует")


    print("[INIT] Готово. Можешь запускать проект.")
    input("Нажми Enter для выхода...")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    setup_project()