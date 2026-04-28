"""
Модели БД для админки «Аксай Гриль».

- Admin: учётная запись администратора (UserMixin для Flask-Login).
- LoginLog: журнал попыток входа (152-ФЗ — ведём аудит доступа).
"""
from __future__ import annotations

from datetime import datetime

import bcrypt
from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session

from app import Base


class Admin(Base, UserMixin):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def set_password(self, password: str) -> None:
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except ValueError:
            return False

    def get_id(self) -> str:
        return str(self.id)


class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True)
    username_attempted = Column(String(128), nullable=False, index=True)
    success = Column(Boolean, default=False, nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


def admins_count(session: Session) -> int:
    return session.query(Admin).count()
