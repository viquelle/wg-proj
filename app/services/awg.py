import base64, subprocess
from config.settings import INTERFACE_NAME, DEBUG
from os import urandom

class AWGError(Exception): pass

def _run(cmd):
    if DEBUG:
        print(f"[DRY RUN] AWG: {cmd}", "DEBUG")
    else:
        subprocess.run(cmd, shell=True, check=True)

def is_valid_key(key: str) -> bool:
    if not isinstance(key, str):
        return False
    if len(key) != 44:
        return False
    try:
        decoded = base64.b64decode(key, validate=True)
    except Exception:
        return False
    return len(decoded) == 32


def generate_keys() -> dict:
    if DEBUG:
        return {"private_key": base64.b64encode(urandom(32)).decode(),
                "public_key": base64.b64encode(urandom(32)).decode()}

    priv = subprocess.check_output(["awg", "genkey"], text=True).strip()
    pub = subprocess.check_output(["awg", "pubkey"], input=priv, text=True).strip()
    return {"private_key": priv, "public_key": pub}


def get_public_key(private_key: str) -> str:
    """Вычисляет публичный ключ из приватного."""
    if not is_valid_key(private_key):
        raise ValueError("Неверный приватный ключ")
    if DEBUG:
        return base64.b64encode(urandom(32)).decode()

    pub = subprocess.check_output(["awg", "pubkey"], input=private_key, text=True).strip()
    return pub

def add_peer(ip: str, public_key: str) -> bool:
    if not is_valid_key(public_key):
        raise ValueError("[AWG.PY | ADD_PEER] Неверный публичный ключ.")
    cmd = f"awg set {INTERFACE_NAME} peer {public_key} allowed-ips {ip}/32"
    try: _run(cmd)
    except subprocess.CalledProcessError as e:
        raise AWGError(f"Ошибка при добавлении клиента в AWG: {e}")
    print(f"AWG Peer добавлен: {ip}")
    return True


def remove_peer(public_key: str) -> bool:
    if not is_valid_key(public_key):
        raise ValueError("[AWG.PY | REMOVE_PEER] Неверный публичный ключ.")

    cmd = f"awg set {INTERFACE_NAME} peer {public_key} remove"

    try:
        _run(cmd)
    except subprocess.CalledProcessError as e:
        raise AWGError(f"Ошибка при удалении клиента в AWG: {e}")
    print(f"AWG Peer удален: {public_key[:8]}...")

    return True
