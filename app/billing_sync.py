#!/usr/bin/env python3
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timezone, timedelta
from database import get_session
from database.models import User
from config.settings import INTERFACE_NAME, SPEED_CEIL


def setup_tc_boot():
    print("[BOOT] Восстановление корневой дисциплины TC...")
    from services import traffic as tc

    try:
        tc._run(f"tc qdisc replace dev {INTERFACE_NAME} root handle 1: htb default 1")
        tc._run(
            f"tc class replace dev {INTERFACE_NAME} parent 1: classid 1:1 htb rate {SPEED_CEIL}Mbit ceil {SPEED_CEIL}Mbit")
    except Exception as e:
        print(f"[BOOT] Пропускаем (возможно, TC уже настроен): {e}")

    print("[BOOT] TC готов.")


def tech_sync():
    """Полная сверка ядра с БД."""
    print("[TECH] Синхронизация ядра с БД...")

    with get_session() as session:
        users = session.query(User).all()
        for user in users:
            user.net_sync()

            for dev in user.devices:
                try:
                    dev.sync()
                except Exception as e:
                    print(f"[TECH] Warn for dev {dev.id}: {e}")

    print("[TECH] Синхронизация завершена.")


def fin_sync():
    print("[FIN] Финансовая синхронизация...")
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    with get_session() as session:
        due_users = session.query(User).filter(User.next_payment <= today).all()

        for user in due_users:
            fee = user.monthly_fee
            if fee <= 0: continue

            user.balance -= fee
            user.next_payment = (today + timedelta(days=30)).replace(tzinfo=timezone.utc)
            user.fin_sync()

        session.commit()
    print(f"[FIN] Обработано пользователей: {len(due_users)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "boot":
        setup_tc_boot()
    elif cmd == "tech":
        tech_sync()
    elif cmd == "fin":
        fin_sync()
    else:
        print("Unexcepted argument")