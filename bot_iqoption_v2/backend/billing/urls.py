from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.subscription_status, name='subscription_status'),
    path('webhook/', views.webhook, name='billing_webhook'),
    path('verify-return/', views.verify_return, name='billing_verify_return'),

    # Admin endpoints (protected by admin email check)
    path('admin/users/', views.admin_users, name='billing_admin_users'),
    path('admin/payments/', views.admin_payments, name='billing_admin_payments'),
    path('admin/grant/', views.admin_grant, name='billing_admin_grant'),
]
