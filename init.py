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

    from app.database import get_session
    from app.database.models import User, UserRoles, Device
    from datetime import datetime, timezone, timedelta
    import config.settings
    import base64

    with get_session() as session:
        admin = session.query(User).filter_by(role=UserRoles.ADMIN).first()
        if not admin:
            admin = User(
                username="Admin",
                role=UserRoles.ADMIN,
                next_payment=datetime.now(timezone.utc) + timedelta(days=365),
                balance=9999.0,
                speed=100,
                description="Удалите или установите валидные данные при запуске вне DEBUG!"
            )
            session.add(admin)
            session.flush()

            trusted_ip = "10.14.201.2" if config.settings.DEBUG else f"{config.settings.SUBNET_PREFIX}2"

            dummy_pub_key = base64.b64encode(b"admin_dummy_pub_key_12345678901234567").decode()

            admin_device = Device(
                ip=trusted_ip,
                name="Admin Workstation",
                public_key=dummy_pub_key,
                user_id=admin.id
            )
            session.add(admin_device)

            print("  ✅ Создан пользователь Admin и его устройство для входа в админку")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    setup_project()