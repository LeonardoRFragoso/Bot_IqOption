from rest_framework import serializers
from .models import Subscription, Payment
from accounts.models import User


class SubscriptionStatusSerializer(serializers.Serializer):
    is_subscribed = serializers.BooleanField()
    active_until = serializers.DateTimeField(allow_null=True)
    preference_id = serializers.CharField(required=False)
    init_point = serializers.CharField(required=False)
    public_key = serializers.CharField(required=False)


class PaymentSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id', 'user', 'user_email', 'mp_payment_id', 'mp_preference_id', 'external_reference',
            'status', 'amount', 'currency', 'description', 'paid_at', 'created_at'
        )
        read_only_fields = ('id', 'created_at', 'paid_at')


class AdminUserSubscriptionSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    active_until = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'is_subscribed', 'active_until', 'date_joined')

    def get_is_subscribed(self, obj):
        sub = getattr(obj, 'subscription', None)
        return sub.is_active() if sub else False

    def get_active_until(self, obj):
        sub = getattr(obj, 'subscription', None)
        return sub.active_until if sub else None
