from rest_framework.permissions import BasePermission


class IsPlatformSuperAdmin(BasePermission):
    """Super Admin access is deliberately separated from the tenant-scoped
    IsBusinessMember permission used everywhere else (master spec section
    4: "Super Admin access separated from tenant access"). Gated on
    is_staff rather than a per-business role — platform staff aren't
    members of any tenant."""

    message = "Super Admin access required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
