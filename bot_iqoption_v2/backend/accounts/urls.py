from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('iq-credentials/', views.set_iq_credentials, name='set_iq_credentials'),
    path('iq-credentials/check/', views.check_iq_credentials, name='check_iq_credentials'),
    path('trading-config/', views.TradingConfigurationView.as_view(), name='trading_config'),
    path('dashboard/', views.dashboard_data, name='dashboard_data'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
