from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class Subscription(models.Model):
    """One active subscription per user. Simplified monthly plan.
    active_until: when the current paid period ends. Consider active if now < active_until
    """
    STATUS_CHOICES = (
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="INACTIVE")
    active_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_subscription"
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def is_active(self) -> bool:
        if self.active_until is None:
            return False
        return timezone.now() < self.active_until

    def activate_for_days(self, days: int = 30):
        now = timezone.now()
        if self.active_until and self.active_until > now:
            self.active_until = self.active_until + timezone.timedelta(days=days)
        else:
            self.active_until = now + timezone.timedelta(days=days)
        self.status = "ACTIVE"
        self.save()


class Payment(models.Model):
    """Mercado Pago payment registry"""

    STATUS_CHOICES = (
        ("approved", "Approved"),
        ("pending", "Pending"),
        ("rejected", "Rejected"),
        ("in_process", "In Process"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
        ("charged_back", "Charged Back"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    mp_payment_id = models.CharField(max_length=64, unique=True)
    mp_preference_id = models.CharField(max_length=64, blank=True, null=True)
    external_reference = models.CharField(max_length=128, blank=True, null=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="BRL")
    description = models.CharField(max_length=255, default="Assinatura Plataforma Bot IQ Option - Mensal")
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_payment"
        ordering = ["-created_at"]

    def mark_as_approved(self):
        self.status = "approved"
        self.paid_at = timezone.now()
        self.save()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_subscription(sender, instance, created, **kwargs):
    """Ensure every user has a Subscription row on creation."""
    if created:
        try:
            Subscription.objects.create(user=instance)
        except Exception:
            # Avoid breaking user creation on any race condition
            pass
