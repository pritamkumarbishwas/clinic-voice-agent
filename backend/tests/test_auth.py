import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip():
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_access_token_round_trip():
    user_id = ObjectId()
    token = create_access_token(
        {
            "_id": user_id,
            "email": "admin@example.com",
            "role": "admin",
        }
    )

    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["email"] == "admin@example.com"
    assert payload["role"] == "admin"


def test_invalid_token_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("not-a-jwt")

    assert exc_info.value.status_code == 401
