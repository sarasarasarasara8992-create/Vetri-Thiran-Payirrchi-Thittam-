from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(512)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow
    )

    histories: Mapped[list["RecommendationHistory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )


class RecommendationHistory(Base):

    __tablename__ = "recommendation_history"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True
    )

    planner: Mapped[str] = mapped_column(
        String(30)
    )

    request_json: Mapped[str] = mapped_column(
        Text
    )

    response_json: Mapped[str] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow
    )

    user: Mapped[User] = relationship(
        back_populates="histories"
    )