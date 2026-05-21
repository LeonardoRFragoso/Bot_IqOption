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
    
    # Advanced Analysis
    path('analysis/best-assets/', views.get_best_assets, name='best_assets'),
    path('analysis/multi-timeframe/', views.get_multi_timeframe_analysis, name='multi_timeframe_analysis'),
    path('analysis/schedule/', views.get_trading_schedule, name='trading_schedule'),
    path('analysis/correlation/', views.get_correlation_status, name='correlation_status'),
    
    # Safety & Controls
    path('safety/loss-tracker/', views.get_loss_tracker_status, name='loss_tracker_status'),
    path('safety/loss-tracker/reset/', views.reset_loss_tracker, name='reset_loss_tracker'),
    path('safety/blacklist/', views.manage_blacklist, name='manage_blacklist'),
    
    # Performance Statistics
    path('performance/strategies/', views.get_strategy_performance, name='strategy_performance'),
    path('performance/daily/', views.get_daily_performance, name='daily_performance'),
    
    # Catalog with filters
    path('catalog/filtered/', views.get_catalog_with_filters, name='catalog_filtered'),
]
