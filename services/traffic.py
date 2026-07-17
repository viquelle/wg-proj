"""
Сервис для работы с traffic control в Linux
"""
import subprocess

from sqlalchemy.sql.coercions import expect

from config.settings import INTERFACE_NAME, SPEED_CEIL, DEBUG
## from config.settings import MIRROR_INTERFACE_NAME
from utils.log import log

PARENT = "1:"
PARENT_CLASS = "1:1"
GUARANTEED_MULT = 0.5

def _run(cmd: str):
    """Выполняет tc-команду. В режиме отладки только логирует."""
    if not DEBUG:
        try:
            subprocess.run(cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            log(f"TC ОШИБКА: {e}", "ERROR")
            raise
    else:
        log(f"[DRY RUN] {cmd}", "DEBUG")
    
## CLASS_ID любого клиента равен 1:1 + ID клиента. Такая логика будет везде.

def setup_user_class(user_id: int, rate: float):
    if rate < 0.002: rate = 0.002
    cmd = f"tc class replace dev {INTERFACE_NAME} parent {PARENT_CLASS} classid {PARENT_CLASS}{user_id} htb rate {rate * GUARANTEED_MULT}Mbit ceil {rate}Mbit"
    _run(cmd)
    log(f"TC User {user_id} -> {rate} Mbit")

def delete_user_class(user_id: int):
    cmd = f"tc class del dev {INTERFACE_NAME} classid {PARENT_CLASS}{user_id}"
    _run(cmd)
 

def setup_device_filter(device_id: int, ip: str, parent_id: int):
    cmd = f"tc filter replace dev {INTERFACE_NAME} protocol ip parent {PARENT} prio {device_id} u32 match ip dst {ip} flowid {PARENT_CLASS}{parent_id}"
    _run(cmd)

def delete_device_filter(device_id: int):
    cmd = f"tc filter del dev {INTERFACE_NAME} parent {PARENT} prio {device_id}"
    try:
        _run(cmd)
    except:
        pass
