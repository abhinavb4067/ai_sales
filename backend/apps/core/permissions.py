from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.core.exceptions import APIError


def resolve_business_for_request(request):
    """Resolve the tenant (Business) for the current authenticated request.

    NEVER trust a business id supplied by the client body/query params for
    authorization purposes. The only inputs used here are:
      - the authenticated user's memberships (dashboard/JWT auth)
      - an `X-Business-ID` header, which is only honored if the
        authenticated user actually has an active membership on that
        business (i.e. it can narrow which of *your* businesses you mean,
        never grant access to someone else's).

    Cached on request._resolved_business for the lifetime of the request.
    """
    if hasattr(request, "_resolved_business"):
        return request._resolved_business

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        request._resolved_business = None
        return None

    memberships = user.memberships.select_related("business").filter(status="active")

    requested_id = request.headers.get("X-Business-ID")
    if requested_id:
        membership = memberships.filter(business_id=requested_id).first()
        if membership is None:
            raise PermissionDenied("You do not have access to this business.")
        request._resolved_membership = membership
        request._resolved_business = membership.business
        return membership.business

    membership = memberships.first()
    if membership is None:
        request._resolved_business = None
        request._resolved_membership = None
        return None

    request._resolved_membership = membership
    request._resolved_business = membership.business
    return membership.business


class IsBusinessMember(BasePermission):
    """Ensures the request resolves to a business the user is an active
    member of. Must be combined with queryset scoping in the view — this
    permission alone does not filter object-level access for list/detail
    views, it only guarantees `request.business` is safe to use."""

    message = "You do not have access to this business."

    def has_permission(self, request, view):
        business = resolve_business_for_request(request)
        if business is None:
            raise APIError(
                code="NO_BUSINESS_CONTEXT",
                message="No business membership found for this account.",
                status_code=403,
            )
        request.business = business
        request.membership = getattr(request, "_resolved_membership", None)
        return True


class HasRole(BasePermission):
    """Factory-style permission: HasRole('owner', 'admin')."""

    allowed_roles: tuple = ()

    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if membership is None:
            return False
        return membership.role in self.allowed_roles

    @classmethod
    def roles(cls, *allowed_roles):
        return type("HasRoleDynamic", (cls,), {"allowed_roles": allowed_roles})


class TenantScopedQuerySetMixin:
    """Mixin for ViewSets/generic views operating on TenantOwnedModel
    subclasses. Guarantees every queryset is filtered to request.business,
    and every create() attaches request.business — regardless of what the
    client sends in the payload.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        business = getattr(self.request, "business", None)
        if business is None:
            return qs.none()
        return qs.filter(business=business)

    def perform_create(self, serializer):
        serializer.save(business=self.request.business)
