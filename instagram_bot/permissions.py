from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from functools import wraps


def admin_or_reception_required(view_func):
    """
    Decorator for views that checks if the user is an admin or receptionist.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_admin or request.user.is_reception):
            return view_func(request, *args, **kwargs)
        else:
            # If user doesn't have permission, redirect to admin login
            return redirect(reverse('admin:login'))
    return _wrapped_view
