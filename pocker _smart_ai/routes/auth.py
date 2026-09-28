from datetime import datetime, timedelta, timezone

import jwt

from fastapi import (
    HTTPException,
    Request
)

from pwdlib import PasswordHash

from sqlalchemy.orm import Session

from app.config import settings
from app.models import User


password_hash = PasswordHash.recommended()

ALGORITHM = "HS256"

COOKIE_NAME = "pocketsmart_token"


def hash_password(password: str) -> str:

    return password_hash.hash(password)


def verify_password(
    password: str,
    hashed: str
) -> bool:

    return password_hash.verify(
        password,
        hashed
    )


def create_token(user_id: int) -> str:

    payload = {
        "sub": str(user_id),
        "exp": (
            datetime.now(timezone.utc)
            + timedelta(hours=24)
        )
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM
    )


def get_current_user(
    request: Request,
    db: Session
) -> User:

    token = request.cookies.get(
        COOKIE_NAME
    )

    if not token:

        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    try:

        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM]
        )

        user_id = int(
            payload["sub"]
        )

    except (
        jwt.PyJWTError,
        KeyError,
        ValueError
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )

    user = db.get(
        User,
        user_id
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user