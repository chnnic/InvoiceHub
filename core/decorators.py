from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

def password_change_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if profile and profile.must_change_password and request.resolver_match and request.resolver_match.url_name != "password_change_required":
            return redirect("password_change_required")
        return view(request, *args, **kwargs)
    return wrapped


def superuser_password_change_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        profile = getattr(request.user, "profile", None)
        if profile and profile.must_change_password:
            url_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
            if url_name not in {"superuser_password", "logout"}:
                return redirect("superuser_password")
        return view(request, *args, **kwargs)
    return wrapped

def tenant_required(roles=None):
    def deco(view):
        @password_change_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            membership=request.user.memberships.filter(active=True).select_related("company").first()
            if not membership: return redirect("signup")
            if roles and membership.role not in roles: raise PermissionDenied
            request.membership=membership; request.company=membership.company
            return view(request, *args, **kwargs)
        return wrapped
    return deco

def superuser_required(view):
    @superuser_password_change_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        return view(request, *args, **kwargs)
    return wrapped
