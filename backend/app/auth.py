import os
import time
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, EmailStr, Field

from app.db import get_conn

JWT_SECRET = os.environ["JWT_SECRET"]
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters")

TOKEN_LIFETIME_SECONDS = 30 * 60
password_hasher = PasswordHasher()
DUMMY_HASH = password_hasher.hash("dummy-password-for-timing")
bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


def make_token(user_id: str) -> str:
    issued_at = int(time.time())
    payload = {
        "sub": user_id,
        "iat": issued_at,
        "exp": issued_at + TOKEN_LIFETIME_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

@router.post("/register")
def register(credentials : Credentials):
    email = credentials.email.lower()
    with get_conn() as connection:
        try:
            new_user = connection.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                (email, password_hasher.hash(credentials.password))
            ).fetchone()
        except UniqueViolation:
            raise HTTPException(400,"Could not register")
        return {"token": make_token(str(new_user[0]))}


@router.post("/login")
def login(credentials: Credentials):
    with get_conn() as connection:
        user_row = connection.execute(
            "SELECT id, password_hash FROM users where email= %s",
        (credentials.email.lower(),),
        ).fetchone()
    #the dummy hashing if the email is unknown
    stored_hash = user_row[1] if user_row else DUMMY_HASH
    try:
        password_hasher.verify(stored_hash, credentials.password)
        login_ok = user_row is not None
    except (VerificationError, InvalidHashError):
        login_ok = False

    if not login_ok:
        raise HTTPException(401,"Invalid email or password")
    return {"token" : make_token(str(user_row[0]))}


def current_user(
    authorization : HTTPAuthorizationCredentials = Depends(bearer_scheme),
)->str:
    if not authorization:
        raise HTTPException(401,"Not authenticated")
    try:
        claims = jwt.decode(
            authorization.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            options = {"require": ["iat","exp", "sub"]},
        )
        user_id = claims["sub"]
        if not isinstance(user_id,str):
            raise ValueError("Invalid Subject")
        return str(uuid.UUID(user_id))
    except(jwt.InvalidTokenError, ValueError, TypeError,KeyError):
        raise HTTPException(401,"Invalid Token")