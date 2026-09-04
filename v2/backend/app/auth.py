from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600000


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return f"{ALGORITHM}:{ITERATIONS}:{salt}:{dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        parts = hashed.split(":")
        if parts[0] != ALGORITHM:
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), iterations)
        return dk.hex() == expected
    except (IndexError, ValueError):
        return False


def create_token(password_hash: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"exp": expire, "sub": "admin", "hash": password_hash[:20]}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str, password_hash: str) -> bool:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload.get("hash") == password_hash[:20]
    except JWTError:
        return False