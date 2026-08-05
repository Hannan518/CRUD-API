import os

import httpx
from errors import TaskError
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

_supabase = None

router = APIRouter(prefix="/auth", tags=["auth"])
info_router = APIRouter(tags=["public"])

security = HTTPBearer(auto_error=False)


class AuthRequest(BaseModel):
    email: str | None = None
    password: str | None = None


def get_credentials(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """Return the Bearer credentials, raising 401 if the header is missing."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise TaskError(401, "Access token required")
    return credentials


def get_supabase():
    """Return a lazily-created Supabase client for the configured project."""
    global _supabase
    if _supabase is None:
        from supabase import create_client

        _supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _supabase


def check_connection():
    """Return True if Supabase Auth is reachable with the configured keys."""
    try:
        url = f"{os.environ['SUPABASE_URL']}/auth/v1/settings"
        response = httpx.get(
            url,
            headers={"apikey": os.environ["SUPABASE_KEY"]},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def _check_credentials(credentials: AuthRequest):
    """Return a 400 error unless both email and password are present."""
    if not credentials.email or not credentials.password:
        raise TaskError(400, "Field 'email' and 'password' are required")


def _map_auth_error(exc: Exception, default_status: int, message: str | None = None):
    """Raise a TaskError from a Supabase/Gotrue exception."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = default_status
    detail = message or getattr(exc, "message", None) or str(exc)
    raise TaskError(status, detail)


def _user_payload(user) -> dict:
    """Return the public user fields used in API responses."""
    return {
        "id": user.id,
        "email": user.email,
        "created_at": getattr(user, "created_at", None),
    }


@router.post("/signup", status_code=201, summary="Register a new user")
def signup(credentials: AuthRequest):
    """Create a new user with Supabase Auth. Returns 400 if fields are missing."""
    _check_credentials(credentials)
    try:
        response = get_supabase().auth.sign_up(
            {"email": credentials.email, "password": credentials.password}
        )
    except Exception as exc:
        _map_auth_error(exc, 400)
    return {"user": _user_payload(response.user)}


@router.post("/login", summary="Log in and receive an access token")
def login(credentials: AuthRequest):
    """Log in with email and password. Returns 401 if the credentials are wrong."""
    _check_credentials(credentials)
    try:
        response = get_supabase().auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )
    except Exception:
        raise TaskError(401, "Invalid login credentials")
    session = response.session
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": "bearer",
        "user": _user_payload(response.user),
    }


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(get_credentials)):
    """Verify the Bearer token and return the authenticated user, else 401."""
    try:
        user = get_supabase().auth.get_user(credentials.credentials).user
    except Exception:
        raise TaskError(401, "Invalid or expired token")
    return user


@router.post("/logout", status_code=204, summary="Log out the current session")
def logout(user=Depends(get_current_user)):
    """Log out the verified session. Best-effort sign-out, returns 204."""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass


@info_router.get("/protected/profile", summary="Get the current user's profile")
def profile(user=Depends(get_current_user)):
    """Return id, email and created_at for the authenticated user."""
    return _user_payload(user)


@info_router.get("/protected/dashboard", summary="Get a protected dashboard greeting")
def dashboard(user=Depends(get_current_user)):
    """Second protected route reusing the same guard - no new auth code."""
    return {"message": f"Welcome, {user.email} - this is your dashboard."}


@info_router.get("/public/info", summary="Public API info")
def public_info():
    """Return API information that does not require authentication."""
    return {"message": "Welcome stranger! This info is public."}
