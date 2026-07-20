import enum
from sqlalchemy.orm import relationship, Session
from database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Float, Text, select
from datetime import datetime, timezone, timedelta
from config.settings import SUBNET_PREFIX
from services.awg import remove_peer
from services.traffic import delete_device_filter


def now_utc():
    return datetime.now(timezone.utc)


class UserRoles(str, enum.Enum):
    REGULAR = "regular"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, default="Пользователь")
    role = Column(Enum(UserRoles), nullable=False, default=UserRoles.REGULAR)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    next_payment = Column(DateTime(timezone=True), nullable=True)
    balance = Column(Float, nullable=False, default=0.0)
    monthly_fee = Column(Float, nullable=False, default=0.0)
    speed = Column(Integer, nullable=False, default=20)
    description = Column(Text, nullable=True, default="")

    devices = relationship("Device", back_populates="owner", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_restricted(self) -> bool:
        return self.monthly_fee != 0 and self.balance <= -self.monthly_fee

    # Методы синхронизации оставлены, но больше не вызываются автоматически в БД
    def net_sync(self):
        from services.traffic import setup_user_class
        setup_user_class(self.id, 1 if self.is_restricted else self.speed)

    def fin_sync(self, session: Session) -> None:
        now = now_utc()
        if self.next_payment is not None:
            next_payment = self.next_payment
            if next_payment.tzinfo is None:
                next_payment = next_payment.replace(tzinfo=timezone.utc)

            if next_payment < now:
                self.add_payment(session, -self.monthly_fee, "Ежемесячная оплата")
                self.next_payment = now + timedelta(days=30)

    def add_payment(self, session: Session, amount: float, desc: str = "") -> None:
        self.balance += amount
        payment = Payment(user_id=self.id, amount=amount, desc=desc, date=now_utc())
        session.add(payment)

    def add_device(self, session: Session, ip: str, name: str, public_key: str, private_key: str = None) -> "Device":
        device = Device(ip=ip, name=name, public_key=public_key, private_key=private_key, user_id=self.id)
        session.add(device)
        session.flush()
        return device

    def change(self, **kwargs) -> None:
        allowed_fields = {"username", "role", "balance", "monthly_fee", "speed", "next_payment", "description"}
        for key, value in kwargs.items():
            if key not in allowed_fields or value is None:
                continue
            if key == "username":
                self.username = str(value)
            elif key == "role":
                self.role = value if isinstance(value, UserRoles) else UserRoles(value)
            elif key == "balance":
                self.balance = float(value)
            elif key == "monthly_fee":
                self.monthly_fee = float(value)
            elif key == "speed":
                self.speed = int(value)  # Убрано self.net_sync()
            elif key == "next_payment":
                if not isinstance(value, datetime): raise ValueError("next_payment должен быть объектом datetime")
                self.next_payment = value
            elif key == "description":
                self.description = str(value)

    @classmethod
    def create(cls, session: Session, username: str = "Пользователь", role: UserRoles = UserRoles.REGULAR,
               next_payment: datetime = None, balance: float = 0.0, monthly_fee: float = 0.0,
               speed: int = 20, description: str = ""):
        if next_payment is None: next_payment = now_utc() + timedelta(days=30)
        user = cls(username=username, role=role, next_payment=next_payment, balance=balance,
                   monthly_fee=monthly_fee, speed=speed, description=description)
        session.add(user)
        session.flush()
        # Убрано user.net_sync()
        return user

    @classmethod
    def get_by_ip(cls, session: Session, ip: str) -> "User":
        device = Device.get_by_ip(session, ip)
        return device.owner if device else None

    @classmethod
    def get_by_id(cls, session: Session, id: int) -> "User":
        return session.scalar(select(cls).where(cls.id == id))

    @classmethod
    def get_all(cls, session: Session) -> list["User"]:
        return list(session.scalars(select(cls)).all())


class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False, default="Устройство")
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    public_key = Column(String, nullable=False, unique=True)
    private_key = Column(String, nullable=True, unique=True)
    owner = relationship("User", back_populates="devices")

    def sync(self):
        from services.awg import add_peer
        from services.traffic import setup_device_filter
        setup_device_filter(self.id, self.ip, self.owner.id)
        add_peer(self.ip, self.public_key)

    def delete(self, session: Session):
        remove_peer(self.public_key)
        delete_device_filter(self.id)
        session.delete(self)

    def change(self, session: Session, **kwargs) -> None:
        old_public_key = self.public_key
        if kwargs.get("ip_suffix") is not None:
            ip_suffix = int(kwargs["ip_suffix"])
            if not (2 <= ip_suffix <= 254): raise ValueError("IP должен быть от 2 до 254")
            new_ip = f"{SUBNET_PREFIX}{ip_suffix}"
            if Device.get_by_ip(session, new_ip) and Device.get_by_ip(session, new_ip).id != self.id: raise ValueError(
                "IP занят")
            self.ip = new_ip
        elif kwargs.get("ip") is not None:
            new_ip = str(kwargs["ip"]).strip()
            if Device.get_by_ip(session, new_ip) and Device.get_by_ip(session, new_ip).id != self.id: raise ValueError(
                "IP занят")
            self.ip = new_ip

        if kwargs.get("name") is not None: self.name = str(kwargs["name"]).strip() or "Устройство"
        if kwargs.get("public_key") is not None:
            from services.awg import is_valid_key
            public_key = str(kwargs["public_key"]).strip()
            if not is_valid_key(public_key): raise ValueError("Ключ некорректный")
            self.public_key = public_key
        session.flush()

    @classmethod
    def get_by_id(cls, session: Session, id: int):
        return session.scalar(select(cls).where(cls.id == id))

    @classmethod
    def get_by_ip(cls, session: Session, ip: str):
        return session.scalar(select(cls).where(cls.ip == ip))

    @classmethod
    def get_all(cls, session: Session):
        return list(session.scalars(select(cls)).all())

    @classmethod
    def get_first_free_ip(cls, session: Session):
        busy = set(row[0] for row in session.query(cls.ip).all())
        for i in range(2, 255):
            ip = f"{SUBNET_PREFIX}{i}"
            if ip not in busy: return ip
        return None


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    desc = Column(String, nullable=True)
    date = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    user = relationship("User", back_populates="payments")

    def change(self, session: Session, **kwargs) -> None:
        for key, value in kwargs.items():
            if value is None: continue
            if key == "amount":
                self.amount = float(value)
            elif key == "desc":
                self.desc = str(value)
            elif key == "date":
                if not isinstance(value, datetime): raise ValueError("date должен быть объектом datetime")
                self.date = value
        session.flush()

    def delete(self, session: Session):
        session.delete(self)

    @classmethod
    def get_all(cls, session: Session):
        return list(session.scalars(select(cls).order_by(cls.date.desc())).all())

    @classmethod
    def get_by_id(cls, session: Session, id: int):
        return session.scalars(select(cls).where(cls.id == id)).first()