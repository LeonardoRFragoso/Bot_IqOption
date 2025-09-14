from rest_framework.permissions import BasePermission
from django.conf import settings


class HasActiveSubscription(BasePermission):
    """Allows access only to users with an active subscription.
    The configured platform admin email bypasses this check.
    """

    message = 'Assinatura ativa requerida para utilizar esta funcionalidade.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Admin bypass
        if getattr(user, 'email', None) == getattr(settings, 'PLATFORM_ADMIN_EMAIL', None):
            return True
        # Subscription check
        sub = getattr(user, 'subscription', None)
        return sub.is_active() if sub else False
