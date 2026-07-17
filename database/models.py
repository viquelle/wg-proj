import enum
from sqlalchemy.orm import relationship, Session

from database import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Float, Text, select
from datetime import datetime, timezone, timedelta
from config.settings import SUBNET_PREFIX


def now_utc():
    return datetime.now(timezone.utc)


class UserRoles(str, enum.Enum):
    ADMIN = "admin"
    REGULAR = "regular"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, default="Пользователь")
    role = Column(Enum(UserRoles), nullable=False, default=UserRoles.REGULAR)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    next_payment = Column(DateTime(timezone=True), nullable=True) 
    balance = Column(Float, nullable=False, default=0.0) 
    monthly_fee = Column(Float, nullable=False, default=0.0)
    speed = Column(Integer, nullable=False, default=0) 

    devices = relationship("Device", back_populates="owner", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user")
    description = relationship("UserDescription", back_populates="user", uselist=False, cascade="all, delete-orphan")


    @property
    def is_restricted(self) -> bool:
        return self.balance <= -self.monthly_fee


    def net_sync(self):
        from services.traffic import setup_user_class
        setup_user_class(self.id, 1 if self.is_restricted else self.speed)

    
    def fin_sync(self):
        now = now_utc()
        if self.next_payment is not None and self.next_payment < now:
            self.balance -= self.monthly_fee
            self.next_payment = now + timedelta(days=30)


    def add_payment(self, session: Session, amount: float, desc: str = "") -> None:
        self.balance += amount
        payment = Payment(user_id=self.id, amount=amount, desc=desc, date=now_utc())
        session.add(payment)
        self.fin_sync()
        self.net_sync()


    def add_device(self, session: Session, ip: str, name: str, public_key: str) -> "Device":
        device = Device(ip=ip, name=name, public_key=public_key, user_id=self.id)
        session.add(device)
        session.flush()
        return device
    

    def change(self, **kwargs) -> None:
        allowed_fields = {
            "username",
            "role",
            "balance",
            "monthly_fee",
            "speed",
            "next_payment",
            "description"
        }
        need_to_fin_sync = False
        need_to_net_sync = False

        for key,value in kwargs.items():
            if key not in allowed_fields:
                continue
            
            if value is None:
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
                self.speed = int(value)
                need_to_net_sync = True

            elif key == "next_payment":
                if not isinstance(value, datetime):
                    raise ValueError("next_payment должен быть объектом datetime")
                self.next_payment = value
                need_to_fin_sync = True

            elif key == "description":
                if self.description:
                    self.description.set(value)
                else:
                    self.description = UserDescription(note=str(value))
        
        if need_to_fin_sync:
            self.fin_sync()
            return
        
        if need_to_net_sync:
            self.net_sync()

        return
    

    @classmethod
    def create(
        cls,
        session: Session,
        username: str = "Пользователь",
        role: UserRoles = UserRoles.REGULAR,
        balance: float = 0.0,
        monthly_fee: float = 0.0,
        speed: int = 0,
        note: str = ""
    ):
        user = cls(
            username=username, 
            role=role,
            balance=balance,
            monthly_fee=monthly_fee,
            speed=speed)
        
        session.add(user)
        session.flush()
        user.description = UserDescription(note=note)
        user.net_sync()

        return user

    @classmethod
    def get_by_ip(cls, session: Session, ip: str) -> User:
        device = Device.get_by_ip(session, ip)
        if not device:
            return None
        return device.owner

    @classmethod
    def get_by_id(cls, session: Session, id: int) -> User:
        return session.scalar(select(cls).where(cls.id == id))

    @classmethod
    def get_all(cls, session: Session) -> list[User]:
        return list(session.scalars(select(cls)).all())


class UserDescription(Base):
    __tablename__ = "user_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    note = Column(Text, nullable=True, default="")
    user = relationship("User", back_populates="description")

    def delete(self, session: Session) -> None:
        session.delete(self)

    def set(self, info: str = "") -> None:
        self.note = str(info)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False, default="Устройство")
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    public_key = Column(String, nullable=False, unique=True)

    owner = relationship("User", back_populates="devices")

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
    def get_busy_ips(cls, session: Session):
        return [row[0] for row in session.query(cls.ip).all()]

    @classmethod
    def get_first_free_ip(cls, session: Session):
        busy = set(cls.get_busy_ips(session))
        for i in range(2, 255):
            ip = f"{SUBNET_PREFIX}{i}"
            if ip not in busy:
                return ip
        return None
    
    @classmethod
    def get_free_ips(cls, session: Session):
        busy = session.scalars(select(cls.ip)).all()
        free = set()
        for i in range(2,255):
            ip = f"{SUBNET_PREFIX}{i}"
            if ip not in busy:
                free.add(ip)
        return free

    def sync(self):
        from services.awg import add_peer
        from services.traffic import setup_device_filter

        setup_device_filter(self.id, self.ip, self.owner.id)
        add_peer(self.ip, self.public_key)

        return
            
    def delete(self, session: Session):
        from services.awg import remove_peer
        from services.traffic import delete_device_filter

        remove_peer(self.public_key)
        delete_device_filter(self.id)
        session.delete(self)

    def change(self, session: Session, **kwargs) -> None:
        allowed_fields = {
            "name",
            "ip",
            "ip_suffix",
            "public_key",
        }

        old_public_key = self.public_key

        for key in kwargs:
            if key not in allowed_fields:
                continue

        # ip_suffix имеет приоритет над ip
        if kwargs.get("ip_suffix") is not None:
            try:
                ip_suffix = int(kwargs["ip_suffix"])
            except (TypeError, ValueError):
                raise ValueError("IP должен быть числом")

            if not (2 <= ip_suffix <= 254):
                raise ValueError("IP должен быть от 2 до 254")

            new_ip = f"{SUBNET_PREFIX}{ip_suffix}"

            busy_device = Device.get_by_ip(session, new_ip)
            if busy_device and busy_device.id != self.id:
                raise ValueError("IP занят")

            self.ip = new_ip


        elif kwargs.get("ip") is not None:
            new_ip = str(kwargs["ip"]).strip()

            busy_device = Device.get_by_ip(session, new_ip)
            if busy_device and busy_device.id != self.id:
                raise ValueError("IP занят")

            self.ip = new_ip

        if kwargs.get("name") is not None:
            self.name = str(kwargs["name"]).strip() or "Устройство"

        if kwargs.get("public_key") is not None:
            from services.awg import is_valid_key, remove_peer

            public_key = str(kwargs["public_key"]).strip()

            if not is_valid_key(public_key):
                raise ValueError("Ключ некорректный")

            self.public_key = public_key

            if old_public_key != self.public_key:
                remove_peer(old_public_key)


        session.flush()



class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    desc = Column(String, nullable=True)
    date = Column(DateTime(timezone=True), nullable=False, default=now_utc)

    user = relationship("User", back_populates="payments")


    @classmethod
    def get_all(cls, session: Session) -> list[Payment]:
        return list(session.scalars(select(cls).order_by(cls.date.desc())).all())

    @classmethod
    def get_by_id(cls, session: Session, id: int) -> Payment:
        return session.scalars(select(cls).where(cls.id == id)).first()

    def change(self, session: Session, **kwargs) -> None:
        allowed_fields = {
            "amount",
            "desc",
            "date",
        }

        for key, value in kwargs.items():
            if key not in allowed_fields:
                continue

            if value is None:
                continue

            if key == "amount":
                new_amount = float(value)

                diff = new_amount - self.amount

                self.amount = new_amount

            elif key == "desc":
                self.desc = str(value)

            elif key == "date":
                if not isinstance(value, datetime):
                    raise ValueError("date должен быть объектом datetime")

                self.date = value

        session.flush()

    def delete(self, session: Session):
        session.delete(self)
