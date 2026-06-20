from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

def tenant_required(roles=None):
    def deco(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            membership=request.user.memberships.filter(active=True).select_related("company").first()
            if not membership: return redirect("signup")
            if roles and membership.role not in roles: raise PermissionDenied
            request.membership=membership; request.company=membership.company
            return view(request, *args, **kwargs)
        return wrapped
    return deco

