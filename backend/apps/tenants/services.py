from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.services import check_plan_limit
from apps.core.exceptions import APIError
from apps.tenants.models import BusinessMembership

INVITABLE_ROLES = {
    BusinessMembership.Role.ADMIN,
    BusinessMembership.Role.SALES,
    BusinessMembership.Role.SUPPORT,
    BusinessMembership.Role.VIEWER,
}


def _active_or_pending_seat_count(business) -> int:
    return BusinessMembership.objects.filter(
        business=business,
        status__in=[BusinessMembership.Status.ACTIVE, BusinessMembership.Status.PENDING],
    ).count()


@transaction.atomic
def invite_member(*, business, email: str, role: str, invited_by: User) -> BusinessMembership:
    if role not in INVITABLE_ROLES:
        raise APIError(code="INVALID_ROLE", message="Cannot invite a member with that role.", status_code=400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        raise APIError(
            code="USER_NOT_REGISTERED",
            message="This person needs to create an account before they can be invited.",
            status_code=404,
        )

    existing = BusinessMembership.objects.filter(business=business, user=user).first()
    if existing and existing.status in (BusinessMembership.Status.ACTIVE, BusinessMembership.Status.PENDING):
        raise APIError(
            code="ALREADY_A_MEMBER",
            message="This person already has an active or pending membership on this business.",
            status_code=400,
        )

    if existing is None:
        check_plan_limit(
            business,
            limit_field="max_team_members",
            current_count=_active_or_pending_seat_count(business),
            resource_name="team members",
        )
        return BusinessMembership.objects.create(
            business=business, user=user, role=role, status=BusinessMembership.Status.PENDING, invited_by=invited_by
        )

    # Re-inviting a previously revoked member reuses the row rather than
    # violating the unique_user_business_membership constraint.
    existing.role = role
    existing.status = BusinessMembership.Status.PENDING
    existing.invited_by = invited_by
    existing.joined_at = None
    existing.save(update_fields=["role", "status", "invited_by", "joined_at", "updated_at"])
    return existing


def accept_invite(*, user: User, membership_id: int) -> BusinessMembership:
    membership = BusinessMembership.objects.filter(
        id=membership_id, user=user, status=BusinessMembership.Status.PENDING
    ).first()
    if membership is None:
        raise APIError(code="INVITE_NOT_FOUND", message="No pending invite found.", status_code=404)

    membership.status = BusinessMembership.Status.ACTIVE
    membership.joined_at = timezone.now()
    membership.save(update_fields=["status", "joined_at", "updated_at"])
    return membership


def revoke_member(*, business, membership_id: int) -> BusinessMembership:
    membership = BusinessMembership.objects.filter(id=membership_id, business=business).first()
    if membership is None:
        raise APIError(code="MEMBERSHIP_NOT_FOUND", message="Membership not found.", status_code=404)

    if membership.role == BusinessMembership.Role.OWNER:
        raise APIError(code="CANNOT_REVOKE_OWNER", message="The business owner cannot be removed.", status_code=400)

    membership.status = BusinessMembership.Status.REVOKED
    membership.save(update_fields=["status", "updated_at"])
    return membership


def change_member_role(*, business, membership_id: int, new_role: str) -> BusinessMembership:
    if new_role not in INVITABLE_ROLES:
        raise APIError(code="INVALID_ROLE", message="Cannot assign that role.", status_code=400)

    membership = BusinessMembership.objects.filter(id=membership_id, business=business).first()
    if membership is None:
        raise APIError(code="MEMBERSHIP_NOT_FOUND", message="Membership not found.", status_code=404)

    if membership.role == BusinessMembership.Role.OWNER:
        raise APIError(code="CANNOT_CHANGE_OWNER_ROLE", message="The owner's role cannot be changed.", status_code=400)

    membership.role = new_role
    membership.save(update_fields=["role", "updated_at"])
    return membership
