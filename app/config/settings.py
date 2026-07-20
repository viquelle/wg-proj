import os
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.getenv("DATABASE_URL")
INTERFACE_NAME = "awg0"
MIRROR_INTERFACE_NAME = "ifb0"
SPEED_CEIL = 600
SUBNET_PREFIX = "10.10.10."
SERVER_PUBLIC_KEY = ""
SERVER_ENDPOINT = "111.222.233.255:10880"
LOCAL_IP = "0.0.0.0"
SERVER_CONFIG_DATA = "\n## Тут можно вставить Jc, Jmax...\n"