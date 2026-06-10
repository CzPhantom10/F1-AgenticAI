"""Circuit ORM model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.db import Base


class Circuit(Base):
    """Formula 1 circuit entity."""

    __tablename__ = "circuits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=False)

    races = relationship("Race", back_populates="circuit")
