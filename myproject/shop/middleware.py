from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import User

from .auth_helpers import verify_token, generate_tokens


class JWTMVTRefreshMiddleware(MiddlewareMixin):

    def process_request(self, request):

        if request.path.startswith("/admin/"):
            return
        
        access_token = request.COOKIES.get("access_token")
        refresh_token = request.COOKIES.get("refresh_token")

        request._new_access_token = None
        request._new_refresh_token = None

        if access_token:
            payload = verify_token(access_token, "access")

            if payload:
                try:
                    request.user = User.objects.get(id=payload["user_id"])
                    return
                except User.DoesNotExist:
                    pass

        if refresh_token:
            refresh_payload = verify_token(refresh_token, "refresh")

            if refresh_payload:
                try:
                    user = User.objects.get(id=refresh_payload["user_id"])
                except User.DoesNotExist:
                    return

                request.user = user

                new_access, new_refresh = generate_tokens(user)

                request._new_access_token = new_access
                request._new_refresh_token = new_refresh

                return

    def process_response(self, request, response):
        if getattr(request, "_new_access_token", None):
            response.set_cookie(
                "access_token",
                request._new_access_token,
                httponly=True,
                samesite="Lax"
            )

            response.set_cookie(
                "refresh_token",
                request._new_refresh_token,
                httponly=True,
                samesite="Lax"
            )

        return response
