from django.contrib import admin
from .models import Subscription, Payment


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'active_until', 'created_at')
    search_fields = ('user__email', 'user__username')
    list_filter = ('status',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'mp_payment_id', 'status', 'amount', 'currency', 'paid_at', 'created_at')
    search_fields = ('user__email', 'mp_payment_id', 'external_reference')
    list_filter = ('status', 'currency')
