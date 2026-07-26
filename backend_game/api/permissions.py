"""
api/permissions.py

All custom DRF permission classes for Role-Based Access Control (RBAC).
Roles come from api.models.User.Role. Permissions are composable: view
classes typically set `permission_classes = [IsAuthenticated, HasRole(...)]`
or use one of the pre-built shortcuts below.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from api.models import User


class HasRole(BasePermission):
    """
    Factory-style permission: HasRole('admin', 'manager') returns a
    permission class instance allowing only those roles (super_admin is
    always implicitly allowed).
    """

    def __init__(self, *allowed_roles):
        self.allowed_roles = set(allowed_roles) | {User.Role.SUPER_ADMIN}

    def __call__(self):
        # DRF instantiates permission classes with no args; this lets the
        # factory itself be dropped straight into permission_classes.
        return self

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.SUPER_ADMIN)


class IsAdminOrManager(BasePermission):
    ALLOWED = {User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.MANAGER}

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in self.ALLOWED)


class IsStaffRole(BasePermission):
    """Any authenticated internal staff member (excludes anonymous portal customers)."""
    ALLOWED = {
        User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.MANAGER,
        User.Role.CASHIER, User.Role.ATTENDANT,
    }

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in self.ALLOWED)


class CanManageFinance(BasePermission):
    """Payments, expenses, reports — restricted to admin/manager/cashier."""
    ALLOWED = {User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.MANAGER, User.Role.CASHIER}

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in self.ALLOWED)


class ReadOnlyOrStaff(BasePermission):
    """Public website endpoints: anyone can read (GET), only staff can write."""
    STAFF_ROLES = {
        User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.MANAGER,
        User.Role.CASHIER, User.Role.ATTENDANT,
    }

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.role in self.STAFF_ROLES)


class IsOwnerOrStaff(BasePermission):
    """Object-level: allow if the requesting user owns the object, or is staff."""
    STAFF_ROLES = {User.Role.SUPER_ADMIN, User.Role.ADMIN, User.Role.MANAGER}

    def has_object_permission(self, request, view, obj):
        if request.user.role in self.STAFF_ROLES:
            return True
        owner_field = getattr(obj, 'recorded_by_id', None) or getattr(obj, 'started_by_id', None)
        return owner_field == request.user.id