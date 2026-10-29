import os
import time
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, EmailStr, Field

from app.db import get_conn
WINDOW_MINUTES = 15
MAX_FAILIURES_PER_EMAIL= 5
MAX_FAILIURES_PER_IP= 20

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
def login(credentials: Credentials, request : Request):
    email = credentials.email.lower()
    ip_address = request.client.host if request.client else "unknown"
    with get_conn() as connection:
        check_not_rate_limited(connection, email, ip_address)
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
    with get_conn() as connection:
        record_attempts(connection, email, ip_address, login_ok)

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


def count_recent_failures(connection, coloumn_name, value):
    return connection.execute(
        f"SELECT COUNT(*) FROM login_attempts where {coloumn_name} = %s "
        "AND succeeded = false AND attempted_at > now() - make_interval(mins => %s)",
        (value, WINDOW_MINUTES),
        ).fetchone()[0]

def check_not_rate_limited(connection, email, ip_address):
    connection.execute(
        "DELETE FROM login_attempts WHERE attempted_at < now() - interval '1 day'")
    too_many_for_email = count_recent_failures(connection, "email", email)>= MAX_FAILIURES_PER_EMAIL
    too_many_for_IP= count_recent_failures(connection, "ip_address", ip_address)>= MAX_FAILIURES_PER_IP

    if too_many_for_email or too_many_for_IP:
        raise HTTPException(429, "Too many attempts. Try again later")

def record_attempts(connection, email, ip_address, succeeded):
    connection.execute(
        "INSERT INTO login_attempts (email, ip_address, succeeded) VALUES (%s, %s, %s)",
        (email,ip_address,succeeded),
    )
    if succeeded:
        connection.execute(
            "DELETE FROM login_attempts WHERE email = %s AND succeeded = false",(email,)
        )
    