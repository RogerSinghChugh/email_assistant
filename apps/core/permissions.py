"""Permission classes — firm-scoped AuthZ with superuser bypass."""

from rest_framework.permissions import BasePermission


def _is_superuser(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return bool(getattr(user, "is_role_superuser", False))


class IsInSameFirm(BasePermission):
    """Require the request user to share a firm_id with the object.

    View-level: requires authentication.
    Object-level: compares `obj.firm_id` (or `obj.firm.id`) with `request.user.firm_id`.
    Superusers always pass.
    """

    message = "You don't have access to resources in this firm."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if _is_superuser(request.user):
            return True
        obj_firm_id = getattr(obj, "firm_id", None) or getattr(
            getattr(obj, "firm", None), "id", None
        )
        return obj_firm_id is not None and str(obj_firm_id) == str(request.user.firm_id)


class IsFirmAdmin(BasePermission):
    """Allow only firm admins (and superusers)."""

    message = "Firm admin role required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if _is_superuser(user):
            return True
        return bool(getattr(user, "is_firm_admin", False))


class IsSuperuser(BasePermission):
    """Allow only superusers."""

    message = "Superuser role required."

    def has_permission(self, request, view) -> bool:
        return _is_superuser(request.user)
