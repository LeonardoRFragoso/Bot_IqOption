from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('iq-credentials/', views.set_iq_credentials, name='set_iq_credentials'),
    path('iq-credentials/check/', views.check_iq_credentials, name='check_iq_credentials'),
    path('trading-config/', views.TradingConfigurationView.as_view(), name='trading_config'),
    path('dashboard/', views.dashboard_data, name='dashboard_data'),
    
    # Notification endpoints
    path('notifications/', views.NotificationListView.as_view(), name='notifications_list'),
    path('notifications/count/', views.notification_count, name='notification_count'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/<int:notification_id>/delete/', views.delete_notification, name='delete_notification'),
    path('notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
]
