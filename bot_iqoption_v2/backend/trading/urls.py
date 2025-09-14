from django.urls import path
from . import views

urlpatterns = [
    # Trading sessions
    path('sessions/', views.TradingSessionListView.as_view(), name='trading_sessions'),
    path('sessions/<uuid:pk>/', views.TradingSessionDetailView.as_view(), name='trading_session_detail'),
    path('sessions/active/', views.get_active_session, name='active_session'),
    
    # Trading control
    path('start/', views.start_trading, name='start_trading'),
    path('stop/', views.stop_trading, name='stop_trading'),
    path('pause/', views.pause_trading, name='pause_trading'),
    path('resume/', views.resume_trading, name='resume_trading'),
    
    # Asset cataloging
    path('catalog/', views.catalog_assets, name='catalog_assets'),
    path('catalog/results/', views.get_catalog_results, name='catalog_results'),
    path('catalog/status/', views.catalog_status, name='catalog_status'),
    
    # Operations
    path('operations/', views.OperationListView.as_view(), name='trading_operations'),
    
    # Logs and monitoring
    path('logs/', views.get_trading_logs, name='trading_logs'),
    path('dashboard/', views.get_dashboard_data, name='dashboard_data'),
    
    # Connection
    path('connection/status/', views.get_connection_status, name='connection_status'),
    path('connection/test/', views.test_connection, name='test_connection'),
    
    # Payouts
    path('payouts/', views.get_payouts, name='get_payouts'),
    
    # Market status
    path('market/status/', views.market_status, name='market_status'),
    
    # Strategies
    path('strategies/', views.get_available_strategies, name='available_strategies'),
]
