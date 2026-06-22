import jwt
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User


def generate_tokens(user):
    now = datetime.utcnow()

    access_payload = {
        "user_id": user.id,
        "token_type": "access",
        "exp": now + timedelta(minutes=15),
        "iat": now,
    }

    refresh_payload = {
        "user_id": user.id,
        "token_type": "refresh",
        "exp": now + timedelta(days=7),
        "iat": now,
    }

    access_token = jwt.encode(
        access_payload,
        settings.SECRET_KEY,
        algorithm="HS256"
    )

    refresh_token = jwt.encode(
        refresh_payload,
        settings.SECRET_KEY,
        algorithm="HS256"
    )

    return access_token, refresh_token


def verify_token(token, expected_type):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )

        if payload.get("token_type") == expected_type:
            return payload

    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        pass

    return None