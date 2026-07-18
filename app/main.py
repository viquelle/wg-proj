from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

import config
from database import get_session
from database.models import User, Device, UserRoles, Payment
from services.awg import generate_keys, is_valid_key, get_public_key
from utils.utils import orn_to_dict
from config.settings import SUBNET_PREFIX, SERVER_CONFIG_DATA

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# --- Pydantic Models (Исправлены опечатки) ---
class UserCreate(BaseModel):
    username: str = "Пользователь"
    role: UserRoles = UserRoles.REGULAR
    next_payment: datetime = datetime.now() + timedelta(days=30)
    balance: float = 0
    monthly_fee: float = 0
    speed: int = 20
    description: str = ""


class UserUpdate(BaseModel):
    username: str | None = None
    role: UserRoles | None = None
    next_payment: datetime | None = None
    balance: float | None = None
    monthly_fee: float | None = None
    speed: int | None = None
    description: str | None = None


class DeviceCreate(BaseModel):
    name: str = "Устройство"
    ip_suffix: int = 0
    public_key: str | None = None


class DeviceUpdate(BaseModel):
    name: str | None = None
    ip_suffix: int | None = None
    public_key: str | None = None


class PaymentCreate(BaseModel):
    amount: float
    desc: str = ""


class PaymentUpdate(BaseModel):
    amount: float | None = None
    desc: str | None = None
    date: datetime | None = None


def get_request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(session, request: Request) -> User | None:
    ip = get_request_ip(request)
    return User.get_by_ip(session, ip) if ip else None


def require_admin(session, request: Request) -> User:
    user = get_current_user(session, request)
    if config.settings.DEBUG: return user
    if not user or user.role != UserRoles.ADMIN:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return user


@app.get("/openapi.json", include_in_schema=False)
def openapi(request: Request):
    with get_session() as session: require_admin(session, request)
    return JSONResponse(get_openapi(title=app.title, version=app.version, routes=app.routes))


@app.get("/docs", include_in_schema=False)
def docs(request: Request):
    with get_session() as session: require_admin(session, request)
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Admin API")


@app.get("/api/admin/users/", summary="Список всех пользователей")
async def admin_get_users(request: Request):
    with get_session() as session:
        require_admin(session, request)
        return [orn_to_dict(u, include_relationships=False) for u in User.get_all(session)]


@app.get("/api/admin/users/var1/{user_id}", summary="Получить пользователя")
async def admin_get_user1(request: Request, user_id: int):
    with get_session() as session:
        require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Не найден")
        return orn_to_dict(user, include_relationships=True)

@app.get("/api/admin/users/var2/{device_id}", summary="Получить пользователя по устройству")
async def admin_get_user2(request: Request, device_id: int):
    with get_session() as session:
        require_admin(session, request)
        device = Device.get_by_id(session, device_id)
        if not device: raise HTTPException(status_code=404, detail="Не найден")
        user = device.owner
        return orn_to_dict(user, include_relationships=True)


@app.post("/api/admin/users/", summary="Создать пользователя")
async def admin_add_user(request: Request, data: UserCreate):
    with get_session() as session:
        require_admin(session, request)
        user = User.create(session, **data.model_dump())
        return orn_to_dict(user, include_relationships=True)


@app.patch("/api/admin/users/{user_id}", summary="Обновить пользователя")
async def admin_edit_user(request: Request, user_id: int, data: UserUpdate):
    with get_session() as session:
        require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Не найден")

        update_data = data.model_dump(exclude_unset=True)
        if "next_payment" in update_data and isinstance(update_data["next_payment"], str):
            update_data["next_payment"] = datetime.fromisoformat(update_data["next_payment"])

        user.change(**update_data)
        return orn_to_dict(user, include_relationships=True)


@app.delete("/api/admin/users/{user_id}", summary="Удалить пользователя")
async def admin_delete_user(request: Request, user_id: int):
    with get_session() as session:
        issuer = require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Не найден")
        if issuer.id == user.id: raise HTTPException(status_code=400, detail="Нельзя удалить себя")

        for device in list(user.devices): device.delete(session)
        session.delete(user)
        return {"ok": True}


@app.get("/api/admin/devices/", summary="Список всех устройств")
async def admin_get_devices(request: Request):
    with get_session() as session:
        require_admin(session, request)
        return [orn_to_dict(d) for d in Device.get_all(session)]

@app.get("/api/admin/devices/var1/{user_id}", summary="Получить устройства пользователя")
async def admin_get_device1(request: Request, user_id: int):
    with get_session() as session:
        require_admin(session, request)
        devices = User.get_by_id(session,user_id).devices
        if not devices: raise HTTPException(status_code=404, detail="Не найдено")
        return [orn_to_dict(d) for d in devices]

@app.get("/api/admin/devices/var2/{device_id}", summary="Получить устройство")
async def admin_get_device2(request: Request, device_id: int):
    with get_session() as session:
        require_admin(session, request)
        device = Device.get_by_id(session, device_id)
        if not device: raise HTTPException(status_code=404, detail="Не найдено")
        return orn_to_dict(device)


@app.post("/api/admin/users/{user_id}/devices", summary="Добавить устройство")
async def admin_add_device(request: Request, user_id: int, data: DeviceCreate):
    with get_session() as session:
        require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Пользователь не найден")

        ip = Device.get_first_free_ip(session) if data.ip_suffix == 0 else f"{SUBNET_PREFIX}{data.ip_suffix}"
        if not ip or Device.get_by_ip(session, ip):
            raise HTTPException(status_code=400, detail="IP занят или недоступен")

        pub_key = data.public_key
        priv_key = None
        if not pub_key:
            keys = generate_keys()
            pub_key, priv_key = keys["public_key"], keys["private_key"]
        elif not is_valid_key(pub_key):
            raise HTTPException(status_code=400, detail="Некорректный ключ")

        device = user.add_device(session, ip=ip, name=data.name, public_key=pub_key, private_key=priv_key)
        device.sync()

        result = orn_to_dict(device)
        if priv_key:
            result["private_key"] = priv_key
            result[
                "config_text"] = f"[Interface]\nPrivateKey = {priv_key}\nAddress = {device.ip}/24\nDNS = 1.1.1.1\n\n[Peer]\nPublicKey = {config.settings.SERVER_PUBLIC_KEY}\nEndpoint = {config.settings.SERVER_ENDPOINT}\nAllowedIPs = 0.0.0.0/0"
        return result


@app.patch("/api/admin/devices/{device_id}", summary="Обновить устройство")
async def admin_edit_device(request: Request, device_id: int, data: DeviceUpdate):
    with get_session() as session:
        require_admin(session, request)
        device = Device.get_by_id(session, device_id)
        if not device: raise HTTPException(status_code=404, detail="Не найдено")
        device.change(session, **data.model_dump(exclude_unset=True))
        return orn_to_dict(device)


@app.delete("/api/admin/devices/{device_id}", summary="Удалить устройство")
async def admin_delete_device(request: Request, device_id: int):
    with get_session() as session:
        require_admin(session, request)
        device = Device.get_by_id(session, device_id)
        if not device: raise HTTPException(status_code=404, detail="Не найдено")
        device.delete(session)
        return {"ok": True}


@app.get("/api/admin/payments/", summary="Список всех платежей")
async def admin_get_payments(request: Request):
    with get_session() as session:
        require_admin(session, request)
        return [orn_to_dict(p) for p in Payment.get_all(session)]


@app.get("/api/admin/users/{user_id}/payments", summary="Платежи пользователя")
async def admin_get_user_payments(request: Request, user_id: int):
    with get_session() as session:
        require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Не найден")
        return [orn_to_dict(p) for p in user.payments]


@app.post("/api/admin/users/{user_id}/payments", summary="Добавить платеж")
async def admin_add_user_payment(request: Request, user_id: int, data: PaymentCreate):
    with get_session() as session:
        require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Не найден")
        user.add_payment(session, amount=data.amount, desc=data.desc)
        return {"ok": True}


@app.patch("/api/admin/payments/{payment_id}", summary="Обновить платеж")
async def admin_edit_payment(request: Request, payment_id: int, data: PaymentUpdate):
    with get_session() as session:
        require_admin(session, request)
        payment = Payment.get_by_id(session, payment_id)
        if not payment: raise HTTPException(status_code=404, detail="Не найден")

        update_data = data.model_dump(exclude_unset=True)
        if "date" in update_data and isinstance(update_data["date"], str):
            update_data["date"] = datetime.fromisoformat(update_data["date"])

        payment.change(session, **update_data)
        return orn_to_dict(payment)


@app.delete("/api/admin/payments/{payment_id}", summary="Удалить платеж")
async def admin_delete_payment(request: Request, payment_id: int):
    with get_session() as session:
        require_admin(session, request)
        payment = Payment.get_by_id(session, payment_id)
        if not payment: raise HTTPException(status_code=404, detail="Не найден")
        payment.delete(session)
        return {"ok": True}


@app.post("/api/admin/sync/finances/all", summary="Проверить и синхронизировать финансы всех пользователей")
async def sync_finances_all(request: Request):
    with get_session() as session:
        require_admin(session, request)
        users = User.get_all(session)
        for user in users:
            user.fin_sync(session)
        session.commit()
        return {"ok": True, "processed": len(users)}


@app.post("/api/admin/sync/finances/{user_id}", summary="Проверить и синхронизировать финансы пользователя")
async def sync_finances_user(request: Request, user_id: int):
    with get_session() as session:
        require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Пользователь не найден")
        user.fin_sync(session)
        session.commit()
        return {"ok": True}

@app.post("/api/admin/sync/tech/all", summary="Тех. синхронизация (AWG/TC) всех пользователей")
async def sync_tech_all(request: Request):
    with get_session() as session:
        require_admin(session, request)
        users = User.get_all(session)
        for user in users:
            user.net_sync()
            for device in user.devices:
                device.sync()
        return {"ok": True, "processed": len(users)}

@app.post("/api/admin/sync/tech/{user_id}", summary="Тех. синхронизация (AWG/TC) пользователя")
async def sync_tech_user(request: Request, user_id: int):
    with get_session() as session:
        require_admin(session, request)
        user = User.get_by_id(session, user_id)
        if not user: raise HTTPException(status_code=404, detail="Пользователь не найден")
        user.net_sync()
        for device in user.devices:
            device.sync()
        return {"ok": True}


class KeyGenerate(BaseModel):
    type: int = 3  # 1 - только приватный, 2 - только публичный, 3 - оба
    private_key: str | None = None  # Опционально: если передать, то публичный будет вычислен из него


@app.post("/api/admin/keys/generate", summary="Сгенерировать ключи AWG: 1 - приватный, 2 - публичный(если передать в аргументе), 3 - оба")
async def admin_generate_keys(request: Request, data: KeyGenerate):
    with get_session() as session:
        require_admin(session, request)

        if data.type not in (1, 2, 3):
            raise HTTPException(status_code=400, detail="type должен быть 1, 2 или 3")

        priv_key = data.private_key
        pub_key = None

        try:
            if data.type == 1:
                if not priv_key:
                    priv_key = generate_keys()["private_key"]
                return {"private_key": priv_key}

            elif data.type == 2:
                if priv_key:
                    pub_key = get_public_key(priv_key)
                else:
                    raise HTTPException(status_code=400, detail="Не передан приватный ключ!")
                return {"public_key": pub_key}

            elif data.type == 3:
                if priv_key:
                    pub_key = get_public_key(priv_key)
                else:
                    keys = generate_keys()
                    priv_key = keys["private_key"]
                    pub_key = keys["public_key"]
                return {"private_key": priv_key, "public_key": pub_key}

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")

@app.get("/api/admin/devices/{device_id}/config", summary="Скачать конфиг устройства")
async def get_device_config(request: Request, device_id: int):
    with get_session() as session:
        require_admin(session, request)

        device = Device.get_by_id(session, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Устройство не найдено")

        config_text = f"""[Interface]
PrivateKey = {device.private_key or "ВСТАВЬТЕ СЮДА КЛЮЧ"}
Address = {device.ip}/24
{SERVER_CONFIG_DATA}

[Peer]
PublicKey = {config.settings.SERVER_PUBLIC_KEY}
Endpoint = {config.settings.SERVER_ENDPOINT}
AllowedIPs = 0.0.0.0/0"""

        return Response(
            content=config_text,
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename={device.owner.id}_{device.id}.conf"}
        )

if __name__ == "__main__":
    uvicorn.run(app, host=config.settings.LOCAL_IP, port=5000)
