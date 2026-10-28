import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, Response, status
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.database import users

PASSWORD_HASH = PasswordHash.recommended()
_DUMMY_HASH = PASSWORD_HASH.hash("invalid-password-placeholder")

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def _credentials_error(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASH.verify(password, password_hash)
    except Exception:
        return False


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def is_valid_email(value: str) -> bool:
    return bool(_EMAIL_PATTERN.fullmatch(normalize_email(value)))


async def authenticate_user(email: str, password: str) -> dict | None:
    normalized = normalize_email(email)
    user = await users.find_one(
        {"email": normalized, "active": True}
    )
    if user is None:
        # Keep the same amount of work for unknown emails.
        verify_password(password, _DUMMY_HASH)
        return None

    if not verify_password(password, user.get("password_hash", "")):
        return None
    return user


def create_access_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user.get("role", "admin"),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise _credentials_error("Invalid or expired token") from exc


def _token_from_request(request: Request) -> str | None:
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        return token

    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return None


def _user_from_document(document: dict) -> CurrentUser:
    return CurrentUser(
        id=str(document["_id"]),
        email=document.get("email", ""),
        name=document.get("name", ""),
        role=document.get("role", "admin"),
    )


async def get_current_user(request: Request) -> CurrentUser:
    token = _token_from_request(request)
    if not token:
        raise _credentials_error()

    payload = decode_access_token(token)
    subject = payload.get("sub")
    if not subject:
        raise _credentials_error("Invalid token subject")

    try:
        user_id = ObjectId(subject)
    except (InvalidId, TypeError) as error:
        raise _credentials_error("Invalid token subject") from error

    user = await users.find_one({"_id": user_id, "active": True})
    if user is None:
        raise _credentials_error("User no longer exists")

    return _user_from_document(user)


async def get_optional_user(request: Request) -> CurrentUser | None:
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


async def require_admin(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def public_user(user: dict | CurrentUser) -> dict:
    if isinstance(user, CurrentUser):
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }
    return {
        "id": str(user["_id"]),
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "role": user.get("role", "admin"),
    }


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
