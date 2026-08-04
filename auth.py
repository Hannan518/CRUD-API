import os

import httpx

_supabase = None


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
