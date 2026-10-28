from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import limiter
from app.auth import (
    CurrentUser,
    LoginRequest,
    authenticate_user,
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    public_user,
    set_auth_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
):
    user = await authenticate_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token = create_access_token(user)
    set_auth_cookie(response, token)
    return {"user": public_user(user)}


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@router.get("/me")
async def current_user(user: CurrentUser = Depends(get_current_user)):
    return {"user": public_user(user)}
