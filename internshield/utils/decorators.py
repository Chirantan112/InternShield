"""Reusable role-based access control decorators."""
from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def role_required(*allowed_roles):
    """Require authentication and one of the supplied application roles.

    Use as @role_required("admin") or @role_required("student", "admin").
    Authentication is enforced before the role check.
    """
    if not allowed_roles or any(role not in {"student", "admin"} for role in allowed_roles):
        raise ValueError("Provide one or more valid application roles.")

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.is_active or current_user.role not in allowed_roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
