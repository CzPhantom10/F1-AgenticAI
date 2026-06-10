"""Declarative base used by all SQLAlchemy ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base ORM class."""

    pass