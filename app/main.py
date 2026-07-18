from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.params import Body
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

import config.settings
from database import get_session
from database.models import User, Device, UserRoles, Payment
from services.awg import generate_keys, is_valid_key
from utils.utils import orn_to_dict
from config.settings import SUBNET_PREFIX

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def get_request_ip(request: Request) -> str | None:
    if config.settings.DEBUG:
        return "10.14.201.2"
    return request.client.host if request.client else None


def get_current_user(session, request: Request) -> User | None:
    ip = get_request_ip(request)
    if not ip:
        return None
    return User.get_by_ip(session, ip)


def is_admin(user: User | None) -> bool:
    return user is not None and user.role == UserRoles.ADMIN

def require_admin(session, request: Request) -> User:
    user = get_current_user(session, request)

    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    return user

@app.get("/", response_class=HTMLResponse)
async def client_page(request: Request):
    return templates.TemplateResponse(request=request, name="client.html", context={})


## ADMIN


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    with get_session() as session:
        user = get_current_user(session, request)
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Недостаточно прав")
    return templates.TemplateResponse(request=request, name="admin.html", context={})


@app.get("/api/admin/bootstrap")
async def admin_bootstrap(request: Request):
    with get_session() as session:
        user = get_current_user(session, request)
        if not is_admin(user):
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        users = sorted(User.get_all(session), key=lambda x: x.id)
        devices = sorted(Device.get_all(session), key=lambda x: x.id)
        payments = Payment.get_all(session)

        return JSONResponse(jsonable_encoder({
            "meta": {
                "roles": [x.value for x in UserRoles]
            },
            "users": [orn_to_dict(u, include_relationships=True) for u in users],
            "devices": [orn_to_dict(device) for device in devices],
            "payments": [orn_to_dict(payment) for payment in payments],
        }))



@app.post("/api/admin/users/", summary="Добавить пользователя")
async def admin_add_user(request: Request):
    with get_session() as session:
        issuer = get_current_user(session, request)
        if not is_admin(issuer):
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        user = User.create(session)
        return JSONResponse(jsonable_encoder(orn_to_dict(user)))


@app.get("/api/admin/users/{user_id}/payments", summary="Получить все платежи пользователя")
async def admin_get_user_payments(request: Request, user_id: int):
    with get_session() as session:
        issuer = get_current_user(session, request)
        if not is_admin(issuer):
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        user = User.get_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        payments = user.payments
        return JSONResponse(jsonable_encoder([orn_to_dict(p) for p in payments]))


@app.post("/api/admin/users/{user_id}/payments", summary="Добавить операцию пользователю")
async def admin_add_user_payment(request: Request, user_id: int, data: dict = Body(examples=[{"amount":0, "desc":"Описание"}])):
    print(data)
    with get_session() as session:
        issuer = get_current_user(session, request)
        if not is_admin(issuer):
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        user = User.get_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        amount = data.get("amount", 0)
        desc = data.get("desc", "")

        user.add_payment(session=session, amount=amount, desc=desc)
        return JSONResponse({"ok": True})


@app.post("/api/admin/users/{user_id}/devices", summary="Добавить устройство пользователю")
async def admin_add_device(request: Request, user_id: int, data: dict = Body(examples=[{"name": "Устройство", "ip_suffix": 0, "public_key": None}])):
    with get_session() as session:
        issuer = get_current_user(session, request)
        if not is_admin(issuer):
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        user = User.get_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        name = str(data.get("name", "Устройство")).strip() or "Устройство"

        try:
            ip_suffix = int(data.get("ip_suffix", 0))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="IP должен быть числом")

        if ip_suffix == 0:
            ip = Device.get_first_free_ip(session)
            if not ip:
                raise HTTPException(status_code=400, detail="Нет свободных IP")
        else:
            if not (2 <= ip_suffix <= 254):
                raise HTTPException(status_code=400, detail="IP должен быть от 2 до 254, либо 0 для авто")
            ip = SUBNET_PREFIX + str(ip_suffix)

        if Device.get_by_ip(session, ip):
            raise HTTPException(status_code=400, detail="IP занят!")

        public_key = data.get("public_key", None)
        if public_key is None:
            keys = generate_keys()
        else:
            if not is_valid_key(public_key):
                raise HTTPException(status_code=400, detail="Ключ некорректный!")
            keys = {"public_key": public_key}

        try:
            device = user.add_device(
                session=session,
                ip=ip,
                name=name,
                public_key=keys["public_key"]
            )
            device.sync()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        result = orn_to_dict(device)
        result["private_key"] = keys.get("private_key", None)

        return JSONResponse(jsonable_encoder(result))


@app.patch("/api/admin/users/{user_id}", summary="Редактировать параметры пользователя")
async def admin_edit_user(request: Request, user_id: int, data: dict = Body(
    examples=[{
            "username": "Иван",
            "role": "regular",
            "balance": 100,
            "monthly_fee": 100,
            "speed": 30,
            "next_payment": "2026-06-01T00:00:00+00:00",
            "description": "Комментарий"
    }]
)):
    with get_session() as session:
        issuer = require_admin(session, request)

        user = User.get_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом JSON")

        if "next_payment" in data and data["next_payment"] is not None:
            try:
                data["next_payment"] = datetime.fromisoformat(data["next_payment"])
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="next_payment должен быть ISO datetime, например 2026-06-01T00:00:00+00:00"
                )

        try:
            user.change(**data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse(jsonable_encoder(orn_to_dict(user, include_relationships=True)))


@app.delete("/api/admin/users/{user_id}", summary="Удалить пользователя")
async def admin_delete_user(request: Request, user_id: int):
    with get_session() as session:
        issuer = require_admin(session, request)

        user = User.get_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if issuer.id == user.id:
            raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")

        try:
            for device in list(user.devices):
                device.delete(session)

            session.delete(user)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse({"ok": True})



@app.delete("/api/admin/devices/{device_id}", summary="Удалить устройство")
async def admin_delete_device(request: Request, device_id: int):
    with get_session() as session:
        require_admin(session, request)

        device = Device.get_by_id(session, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Устройство не найдено")

        try:
            device.delete(session)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse({"ok": True})

@app.patch("/api/admin/devices/{device_id}", summary="Изменить устройство")
async def admin_edit_device(request: Request, device_id: int, data: dict = Body(
        examples=[
            {
                "name": "Телефон",
                "status": "active",
                "ip_suffix": 15,
                "public_key": None
            }
        ]
    )
):
    with get_session() as session:
        require_admin(session, request)

        device = Device.get_by_id(session, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Устройство не найдено")

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Тело запроса должно быть JSON-объектом")

        try:
            device.change(session=session, **data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse(jsonable_encoder(orn_to_dict(device)))



@app.patch(
    "/api/admin/payments/{payment_id}",
    summary="Изменить платеж"
)
async def admin_edit_payment(
    request: Request,
    payment_id: int,
    data: dict = Body(
        ...,
        examples=[
            {
                "amount": 150,
                "desc": "Исправленная оплата",
                "date": "2026-06-01T00:00:00+00:00"
            }
        ]
    )
):
    with get_session() as session:
        require_admin(session, request)

        payment = Payment.get_by_id(session, payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Платеж не найден")

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Тело запроса должно быть JSON-объектом")

        if "date" in data and data["date"] is not None:
            try:
                data["date"] = datetime.fromisoformat(data["date"])
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="date должен быть ISO datetime, например 2026-06-01T00:00:00+00:00"
                )

        try:
            payment.change(session=session, **data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse(jsonable_encoder(orn_to_dict(payment)))


@app.delete(
    "/api/admin/payments/{payment_id}",
    summary="Удалить платеж"
)
async def admin_delete_payment(request: Request, payment_id: int):
    with get_session() as session:
        require_admin(session, request)

        payment = Payment.get_by_id(session, payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Платеж не найден")

        try:
            payment.delete(session)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse({"ok": True})