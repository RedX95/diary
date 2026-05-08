import os
from dotenv import load_dotenv
from supabase import Client, ClientOptions, create_client

load_dotenv()


def get_supabase_client(access_token: str | None = None) -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY are not set")

    headers: dict[str, str] = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    return create_client(url, key, options=ClientOptions(headers=headers))


def sign_in_with_password(email: str, password: str) -> dict:
    client = get_supabase_client()
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    return res.model_dump() if hasattr(res, "model_dump") else res


def sign_up(email: str, password: str) -> dict:
    client = get_supabase_client()
    res = client.auth.sign_up({"email": email, "password": password})
    return res.model_dump() if hasattr(res, "model_dump") else res


def get_user(access_token: str) -> dict:
    client = get_supabase_client(access_token=access_token)
    user = client.auth.get_user(access_token)
    return user.model_dump() if hasattr(user, "model_dump") else user
