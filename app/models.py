from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    manychat_id = Column(String(50), nullable=True, index=True)
    name = Column(String(100), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    status = Column(String(20), default="pending")
    total = Column(Float, default=0.0)
    notes = Column(Text, default="")
    pickup_time = Column(String(50), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_name = Column(String(100), nullable=False)
    category = Column(String(50), default="")
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0.0)
    notes = Column(String(200), default="")
    subtotal = Column(Float, default=0.0)

    order = relationship("Order", back_populates="items")


engine = None
SessionLocal = None


def init_engine(database_url: str):
    global engine, SessionLocal
    if database_url and database_url.startswith("sqlite"):
        path = database_url.replace("sqlite:///", "").strip()
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url or "sqlite:///data/restaurant.db", echo=False)
    SessionLocal = sessionmaker(bind=engine)


def init_db():
    if engine is None:
        raise RuntimeError("init_engine() must be called before init_db()")
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception:
        pass
