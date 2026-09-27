from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import LoginSerializer, RegisterSerializer, UserSerializer
from apps.core.exceptions import APIError


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = _tokens_for_user(user)
        return Response(
            {
                "success": True,
                "user": UserSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = _tokens_for_user(user)
        return Response(
            {
                "success": True,
                "user": UserSerializer(user).data,
                "tokens": tokens,
            }
        )


class RefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            raise APIError("REFRESH_TOKEN_REQUIRED", "Refresh token is required.", 400)
        try:
            old_refresh = RefreshToken(refresh_token)
            access = str(old_refresh.access_token)
            user_id = old_refresh["user_id"]
        except TokenError as exc:
            raise APIError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired.", 401) from exc

        # ROTATE_REFRESH_TOKENS=True + BLACKLIST_AFTER_ROTATION=True: issue a
        # brand new refresh token and blacklist the one just used, so a
        # stolen refresh token can only be replayed once.
        from apps.accounts.models import User

        user = User.objects.get(pk=user_id)
        old_refresh.blacklist()
        new_tokens = _tokens_for_user(user)
        return Response({"success": True, "tokens": {"access": access, **new_tokens}})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            raise APIError("REFRESH_TOKEN_REQUIRED", "Refresh token is required.", 400)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            raise APIError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired.", 400) from exc
        return Response({"success": True}, status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"success": True, "user": UserSerializer(request.user).data})
