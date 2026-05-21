from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import timedelta, datetime
import threading
import time

from .models import TradingSession, Operation, AssetCatalog, TradingLog, MarketData
from billing.permissions import HasActiveSubscription
from .serializers import (
    TradingSessionSerializer, OperationSerializer, AssetCatalogSerializer,
    TradingLogSerializer, StartTradingSerializer, StopTradingSerializer,
    CatalogAssetsSerializer, DashboardDataSerializer, SessionStatsSerializer
)
from .iq_api import IQOptionManager
from .strategies import get_strategy, get_strategy_info
from .catalog import AssetCatalogService

# In-memory catalog status per user to avoid fragile log parsing on the frontend
# Structure: { user_id: { 'running': bool, 'last_started': datetime, 'last_completed': datetime } }
catalog_status_map = {}


# Global dictionary to store running trading threads
trading_threads = {}

# In-memory guard to prevent duplicate session starts per user
_start_guard_mutex = threading.RLock()
_user_start_locks = {}

def _get_user_start_lock(user_id):
    """Return a per-user start lock, creating it if necessary in a thread-safe way."""
    with _start_guard_mutex:
        lock = _user_start_locks.get(user_id)
        if lock is None:
            lock = threading.RLock()
            _user_start_locks[user_id] = lock
        return lock


def run_trading_loop(user, session, strategy, api):
    """Background loop to run a trading strategy for a session.
    Ensures proper cleanup, logging and API disconnection.
    """
    try:
        strategy.start()
        strategy.run(session.asset)
    except Exception as e:
        session.status = 'ERROR'
        session.save()
        TradingLog.objects.create(
            session=session,
            user=user,
            level='ERROR',
            message=f'Erro na execução da estratégia: {str(e)}'
        )
    finally:
        strategy.stop()
        if session.status == 'RUNNING':
            session.status = 'STOPPED'
            session.stopped_at = timezone.now()
            session.save()
            # Broadcast session stopped to frontend
            try:
                from channels.layers import get_channel_layer
                from asgiref.sync import async_to_sync
                from .serializers import TradingSessionSerializer
                channel_layer = get_channel_layer()
                if channel_layer:
                    group = f"trading_{user.id}"
                    sess_payload = TradingSessionSerializer(session).data
                    async_to_sync(channel_layer.group_send)(group, {
                        'type': 'session_update',
                        'data': sess_payload,
                    })
            except Exception:
                pass
        # Remove from active threads (idempotent, avoid race conditions)
        try:
            trading_threads.pop(session.id, None)
        except Exception:
            pass
        # Disconnect and drop the API instance to avoid lingering sessions
        try:
            if api:
                api.disconnect()
        except Exception:
            pass
        try:
            IQOptionManager.remove_instance(user)
        except Exception:
            pass

class TradingSessionListView(generics.ListAPIView):
    """List user's trading sessions"""
    
    serializer_class = TradingSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return TradingSession.objects.filter(user=self.request.user)


class TradingSessionDetailView(generics.RetrieveAPIView):
    """Get trading session details"""
    
    serializer_class = TradingSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return TradingSession.objects.filter(user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, HasActiveSubscription])
def start_trading(request):
    """Start a new trading session"""
    
    serializer = StartTradingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user

    # Acquire per-user start lock to prevent duplicate starts under concurrent requests
    user_lock = _get_user_start_lock(user.id)
    acquired = user_lock.acquire(timeout=5)
    if not acquired:
        return Response(
            {'error': 'Outra inicialização de sessão está em andamento. Tente novamente em alguns segundos.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    try:
        # Check if user already has an active session (guarded by lock)
        active_session = TradingSession.objects.filter(
            user=user,
            status__in=['RUNNING', 'PAUSED']
        ).first()
        
        if active_session:
            return Response(
                {'error': 'Você já possui uma sessão ativa. Pare a sessão atual antes de iniciar uma nova.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get IQ Option API instance
        api = IQOptionManager.get_instance(user)
        if not api:
            return Response(
                {'error': 'Credenciais da IQ Option não configuradas.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Connect to IQ Option
        success, message = api.connect()
        if not success:
            return Response(
                {'error': f'Falha na conexão com IQ Option: {message}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Change account type
        account_type = serializer.validated_data['account_type']
        success, message = api.change_account(account_type)
        if not success:
            return Response(
                {'error': f'Falha ao trocar conta: {message}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create trading session
        session = TradingSession.objects.create(
            user=user,
            strategy=serializer.validated_data['strategy'],
            asset=serializer.validated_data['asset'],
            account_type=account_type,
            initial_balance=api.get_balance(),
            current_balance=api.get_balance(),
            status='RUNNING'
        )
        
        # Start trading in background thread
        strategy = get_strategy(session.strategy, api, session)
        if not strategy:
            session.delete()
            return Response(
                {'error': 'Estratégia não encontrada.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        thread = threading.Thread(target=run_trading_loop, args=(user, session, strategy, api))
        thread.daemon = True
        thread.start()
        
        # Store thread reference
        trading_threads[session.id] = {
            'thread': thread,
            'strategy': strategy,
            'api': api
        }
        
        return Response(TradingSessionSerializer(session).data, status=status.HTTP_201_CREATED)
    finally:
        try:
            user_lock.release()
        except Exception:
            pass


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, HasActiveSubscription])
def pause_trading(request):
    """Pause active trading session"""
    
    serializer = StopTradingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    session_id = serializer.validated_data['session_id']
    session = get_object_or_404(
        TradingSession,
        id=session_id,
        user=request.user,
        status='RUNNING'
    )
    
    # Pause strategy if running
    if session_id in trading_threads:
        thread_info = trading_threads[session_id]
        strategy = thread_info['strategy']
        strategy.running = False  # Pause the strategy loop
    
    # Update session status
    session.status = 'PAUSED'
    session.save()
    
    return Response({
        'message': 'Sessão pausada com sucesso',
        'session': TradingSessionSerializer(session).data
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, HasActiveSubscription])
def resume_trading(request):
    """Resume paused trading session"""
    
    serializer = StopTradingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    session_id = serializer.validated_data['session_id']
    session = get_object_or_404(
        TradingSession,
        id=session_id,
        user=request.user,
        status='PAUSED'
    )
    
    # Resume strategy if exists
    if session_id in trading_threads:
        thread_info = trading_threads[session_id]
        strategy = thread_info['strategy']
        strategy.running = True  # Resume the strategy loop
    else:
        # Restart the strategy if thread was lost
        api = IQOptionManager.get_instance(request.user)
        if not api:
            return Response(
                {'error': 'Credenciais da IQ Option não configuradas.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success, message = api.connect()
        if not success:
            return Response(
                {'error': f'Falha na conexão com IQ Option: {message}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start new trading thread
        strategy = get_strategy(session.strategy, api, session)
        if not strategy:
            return Response(
                {'error': 'Estratégia não encontrada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        thread = threading.Thread(target=run_trading_loop, args=(request.user, session, strategy, api))
        thread.daemon = True
        thread.start()
        
        trading_threads[session_id] = {
            'thread': thread,
            'strategy': strategy,
            'started_at': timezone.now()
        }
    
    # Update session status
    session.status = 'RUNNING'
    session.save()
    
    return Response({
        'message': 'Sessão retomada com sucesso',
        'session': TradingSessionSerializer(session).data
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, HasActiveSubscription])
def stop_trading(request):
    """Stop active trading session"""
    
    serializer = StopTradingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    session_id = serializer.validated_data['session_id']
    # Make this endpoint idempotent: do not restrict by status
    session = TradingSession.objects.filter(
        id=session_id,
        user=request.user,
    ).first()
    if not session:
        # If the session does not exist or does not belong to the user, treat as no-op
        return Response({'message': 'Sessão não encontrada; nada para parar.'})
    
    # Stop strategy if running (race-safe)
    thread_info = trading_threads.get(session_id)
    if thread_info:
        try:
            strategy = thread_info.get('strategy')
            if strategy:
                strategy.stop()
            # Wait for thread to finish (max 10 seconds)
            t = thread_info.get('thread')
            if t:
                t.join(timeout=10)
        except Exception:
            pass
        finally:
            # Safe removal even if another cleanup already removed it
            try:
                trading_threads.pop(session_id, None)
            except Exception:
                pass
    
    # Update session status idempotently
    if session.status != 'STOPPED':
        session.status = 'STOPPED'
        session.stopped_at = timezone.now()
        session.save()
        # Broadcast session stopped to frontend
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from .serializers import TradingSessionSerializer
            channel_layer = get_channel_layer()
            if channel_layer:
                group = f"trading_{request.user.id}"
                sess_payload = TradingSessionSerializer(session).data
                async_to_sync(channel_layer.group_send)(group, {
                    'type': 'session_update',
                    'data': sess_payload,
                })
        except Exception:
            pass
    # Proactively disconnect and remove API instance when user stops trading
    try:
        IQOptionManager.remove_instance(request.user)
    except Exception:
        pass
    
    return Response({'message': 'Sessão de trading parada com sucesso.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_active_session(request):
    """Get user's active trading session"""
    # Cleanup: if there are sessions marked RUNNING but no background thread, stop them
    try:
        running_sessions = TradingSession.objects.filter(user=request.user, status='RUNNING')
        for sess in running_sessions:
            if sess.id not in trading_threads:
                sess.status = 'STOPPED'
                sess.stopped_at = timezone.now()
                sess.save()
    except Exception:
        pass

    session = TradingSession.objects.filter(
        user=request.user,
        status__in=['RUNNING', 'PAUSED']
    ).first()

    if session:
        return Response(TradingSessionSerializer(session).data)
    return Response({'session': None})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, HasActiveSubscription])
def catalog_assets(request):
    """Catalog assets for strategies"""
    
    serializer = CatalogAssetsSerializer(data=request.data)
    if not serializer.is_valid():
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Catalog serializer validation error: {serializer.errors}, data: {request.data}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    
    # Get IQ Option API instance
    api = IQOptionManager.get_instance(user)
    if not api:
        return Response(
            {'error': 'Credenciais da IQ Option não configuradas.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Connect to IQ Option
    success, message = api.connect()
    if not success:
        return Response(
            {'error': f'Falha na conexão com IQ Option: {message}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Change account type
    account_type = serializer.validated_data['account_type']
    success, message = api.change_account(account_type)
    if not success:
        return Response(
            {'error': f'Falha ao trocar conta: {message}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Mark status as running
    try:
        catalog_status_map[user.id] = {
            'running': True,
            'last_started': timezone.now(),
            'last_completed': catalog_status_map.get(user.id, {}).get('last_completed')
        }
    except Exception:
        pass

    # Run cataloging in background
    def run_cataloging():
        try:
            catalog_service = AssetCatalogService(api, user)
            strategies = serializer.validated_data['strategies']
            catalog_service.catalog_assets(strategies)
        except Exception as e:
            TradingLog.objects.create(
                user=user,
                level='ERROR',
                message=f'Erro na catalogação: {str(e)}'
            )
        finally:
            # Update catalog status as completed
            try:
                catalog_status_map[user.id] = {
                    'running': False,
                    'last_started': catalog_status_map.get(user.id, {}).get('last_started'),
                    'last_completed': timezone.now(),
                }
            except Exception:
                pass
            # Disconnect from IQ Option to prevent heavy calls during dashboard refresh
            try:
                api.disconnect()
            except Exception:
                pass
            # Ensure manager drops the instance so subsequent endpoints see disconnected state
            try:
                IQOptionManager.remove_instance(user)
            except Exception:
                pass
    
    thread = threading.Thread(target=run_cataloging)
    thread.daemon = True
    thread.start()
    
    return Response({'message': 'Catalogação iniciada. Verifique os logs para acompanhar o progresso.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_catalog_results(request):
    """Get asset catalog results - returns only the most recent analysis for each asset+strategy"""
    from django.db.models import Max
    
    # Filter only main strategies (mhi, torres_gemeas, mhi_m5)
    main_strategies = ['mhi', 'torres_gemeas', 'mhi_m5']
    
    # Get the most recent entry for MAIN strategies to determine the session
    latest_main = AssetCatalog.objects.filter(
        user=request.user,
        strategy__in=main_strategies
    ).order_by('-analyzed_at').first()
    
    if not latest_main:
        return Response([])
    
    # Get all entries from the same cataloging session (within 10 minutes of the latest main strategy entry)
    from datetime import timedelta
    session_start = latest_main.analyzed_at - timedelta(minutes=10)
    
    catalogs = AssetCatalog.objects.filter(
        user=request.user,
        analyzed_at__gte=session_start,
        strategy__in=main_strategies
    ).order_by('-gale3_rate', '-analyzed_at')
    
    serializer = AssetCatalogSerializer(catalogs, many=True)
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def catalog_status(request):
    """Return current catalog status for the authenticated user.
    Response: { running: bool, last_started?: iso, last_completed?: iso }
    """
    user = request.user
    state = catalog_status_map.get(user.id, {})

    # Fallback last_completed based on database if not present in memory
    last_completed = state.get('last_completed')
    if not last_completed:
        try:
            last = AssetCatalog.objects.filter(user=user).order_by('-analyzed_at').values_list('analyzed_at', flat=True).first()
            last_completed = last
        except Exception:
            last_completed = None

    return Response({
        'running': bool(state.get('running', False)),
        'last_started': state.get('last_started'),
        'last_completed': last_completed,
    })


class OperationListView(generics.ListAPIView):
    """List user's trading operations"""
    
    serializer_class = OperationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    
    def get_queryset(self):
        qs = Operation.objects.filter(session__user=self.request.user)
        session_id = self.request.query_params.get('session')
        if session_id:
            try:
                qs = qs.filter(session_id=session_id)
            except Exception:
                pass
        return qs.order_by('-created_at')


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_trading_logs(request):
    """Get trading logs for user"""
    
    session_id = request.query_params.get('session_id')
    
    logs = TradingLog.objects.filter(user=request.user)
    
    if session_id:
        logs = logs.filter(session_id=session_id)
    
    logs = logs.order_by('-created_at')[:100]  # Last 100 logs
    
    serializer = TradingLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_dashboard_data(request):
    """Get comprehensive dashboard data"""
    
    user = request.user
    
    # Current active session
    current_session = TradingSession.objects.filter(
        user=user,
        status__in=['RUNNING', 'PAUSED']
    ).first()
    
    # All user operations (used for KPIs) and recent slice for UI table
    all_operations_qs = Operation.objects.filter(session__user=user)
    recent_operations = all_operations_qs.order_by('-created_at')[:20]
    
    # Session statistics
    sessions = TradingSession.objects.filter(user=user)
    total_sessions = sessions.count()
    active_sessions = sessions.filter(status__in=['RUNNING', 'PAUSED']).count()
    
    # Financial statistics
    total_profit = sessions.aggregate(
        total=Sum('total_profit')
    )['total'] or 0
    
    # Prefer counting operations from Operation table for accuracy
    total_operations = all_operations_qs.count()
    total_wins = all_operations_qs.filter(result='WIN').count()
    total_losses = all_operations_qs.filter(result='LOSS').count()
    overall_win_rate = (total_wins / total_operations * 100) if total_operations > 0 else 0
    
    # Best performing strategy and asset
    best_strategy_data = sessions.values('strategy').annotate(
        avg_profit=Avg('total_profit'),
        total_ops=Sum('total_operations')
    ).filter(total_ops__gt=0).order_by('-avg_profit').first()
    
    best_asset_data = sessions.values('asset').annotate(
        avg_profit=Avg('total_profit'),
        total_ops=Sum('total_operations')
    ).filter(total_ops__gt=0).order_by('-avg_profit').first()
    
    session_stats = {
        'total_sessions': total_sessions,
        'active_sessions': active_sessions,
        'total_profit': total_profit,
        'total_operations': total_operations,
        'overall_win_rate': round(overall_win_rate, 2),
        'best_strategy': best_strategy_data['strategy'] if best_strategy_data else 'N/A',
        'best_asset': best_asset_data['asset'] if best_asset_data else 'N/A'
    }
    
    # Recent logs (last 50)
    recent_logs = TradingLog.objects.filter(user=user).order_by('-created_at')[:50]
    
    # Account balance and connection status
    api = IQOptionManager.get_instance(user)
    account_balance = 0
    connection_status = False
    
    if api:
        connection_status = api.connected
        if connection_status:
            account_balance = api.get_balance()
    # Fallback: if not connected (e.g., dev server reload), use session's stored balance
    if (not account_balance) or (float(account_balance) == 0.0):
        try:
            if current_session and current_session.current_balance is not None:
                account_balance = float(current_session.current_balance)
            elif not current_session:
                last_session = TradingSession.objects.filter(user=user).order_by('-started_at').first()
                if last_session and last_session.current_balance is not None:
                    account_balance = float(last_session.current_balance)
        except Exception:
            pass
    
    # Intraday P&L and performance series (use explicit local day boundaries to avoid TZ mismatches)
    now_local = timezone.localtime()
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    todays_ops_qs = (
        all_operations_qs
        .filter(created_at__gte=start_of_day, created_at__lt=end_of_day)
        .order_by('created_at')
    )
    todays_ops = list(todays_ops_qs)
    # Sum today's P&L first
    total_today = 0.0
    for op in todays_ops:
        try:
            total_today += float(op.profit_loss)
        except Exception:
            pass
    pnl_today = round(total_today, 2)
    # Estimate start-of-day balance to build a realistic balance curve
    try:
        start_of_day_balance = float(account_balance) - pnl_today
    except Exception:
        start_of_day_balance = 0.0
    performance_data = []
    running_pnl = 0.0
    for op in todays_ops:
        try:
            pl = float(op.profit_loss)
        except Exception:
            pl = 0.0
        running_pnl += pl
        current_balance_point = start_of_day_balance + running_pnl
        performance_data.append({
            'time': op.created_at.strftime('%H:%M'),
            'pnl': round(running_pnl, 2),
            'balance': round(current_balance_point, 2),
            'operations': 1
        })
    
    # Strategy performance summary
    strategy_rows = sessions.values('strategy').annotate(
        ops=Sum('total_operations'),
        wins=Sum('wins'),
        profit=Sum('total_profit')
    ).filter(ops__gt=0)
    strategy_performance = []
    for row in strategy_rows:
        ops = row['ops'] or 0
        wins = row['wins'] or 0
        profit = float(row['profit'] or 0)
        win_rate = round((wins / ops * 100), 2) if ops > 0 else 0
        strategy_performance.append({
            'name': row['strategy'],
            'winRate': win_rate,
            'operations': ops,
            'profit': profit,
        })
    
    dashboard_data = {
        'current_session': TradingSessionSerializer(current_session).data if current_session else None,
        'recent_operations': OperationSerializer(recent_operations, many=True).data,
        'session_stats': session_stats,
        'recent_logs': TradingLogSerializer(recent_logs, many=True).data,
        'account_balance': account_balance,
        'connection_status': connection_status,
        # Aliases and extended KPIs expected by frontend
        'balance': account_balance,
        'pnl_today': pnl_today,
        'total_operations': total_operations,
        'win_rate': round(overall_win_rate, 2),
        'wins': total_wins,
        'losses': total_losses,
        'performance_data': performance_data,
        'strategy_performance': strategy_performance,
        # Back-compat optional aliases
        'total_balance': account_balance,
        'today_profit_loss': pnl_today,
    }
    
    return Response(dashboard_data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_connection_status(request):
    """Get IQ Option connection status"""
    
    user = request.user
    api = IQOptionManager.get_instance(user)
    
    if not api:
        return Response({
            'connected': False,
            'message': 'Credenciais não configuradas'
        })
    
    return Response({
        'connected': api.connected,
        'balance': api.get_balance() if api.connected else 0,
        'account_type': api.account_type if api.connected else None
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def test_connection(request):
    """Test IQ Option connection"""
    
    user = request.user
    api = IQOptionManager.get_instance(user)
    
    if not api:
        return Response(
            {'error': 'Credenciais da IQ Option não configuradas.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    success, message = api.connect()
    
    if success:
        balance = api.get_balance()
        profile = api.get_profile()
        
        return Response({
            'success': True,
            'message': message,
            'balance': balance,
            'currency': profile.get('currency_char', '$') if profile else '$'
        })
    else:
        return Response(
            {'error': message},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def market_status(request):
    """Get current market status and trading hours information"""
    try:
        api = IQOptionManager.get_instance(request.user)

        # Always provide time-based market_info; avoid contacting platform unless connected
        if api:
            market_info = api.get_market_status_info()
        else:
            # Fallback time info if API instance is unavailable
            now_utc = datetime.now(timezone.utc)
            ny_time = now_utc - timedelta(hours=5)
            london_time = now_utc + timedelta(hours=0)
            tokyo_time = now_utc + timedelta(hours=9)
            market_info = {
                'current_utc': now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),
                'new_york': ny_time.strftime('%H:%M EST'),
                'london': london_time.strftime('%H:%M GMT'),
                'tokyo': tokyo_time.strftime('%H:%M JST'),
                'is_weekend': now_utc.weekday() >= 5,
                'forex_open': True,
                'us_stocks_open': False,
            }

        # Get cataloged assets as fallback when not connected
        cataloged_assets = list(
            AssetCatalog.objects.filter(user=request.user)
            .values_list('asset', flat=True)
            .distinct()
            .order_by('asset')[:20]
        )
        
        # OTC markets are always open (24/7)
        otc_assets = [a for a in cataloged_assets if '-OTC' in a]
        binary_open = len(otc_assets) > 0 or not market_info.get('is_weekend', False)

        # If not connected, show cataloged assets
        if not api or not api.connected:
            # Get best asset from catalog
            best_catalog = AssetCatalog.objects.filter(user=request.user).order_by('-gale2_rate').first()
            best_asset = best_catalog.asset if best_catalog else None
            
            return Response({
                'market_info': market_info,
                'open_assets_count': len(cataloged_assets),
                'open_assets': cataloged_assets[:10],
                'best_asset': best_asset,
                'recommendations': {
                    'forex_trading': market_info.get('forex_open', False),
                    'stock_trading': market_info.get('us_stocks_open', False),
                    'binary_trading': binary_open,
                    'weekend_mode': market_info.get('is_weekend', False)
                }
            })

        # Connected: safe to query live info
        open_assets = api.get_open_assets()
        best_asset = api.get_best_available_asset()
        
        # If no live assets, use cataloged
        if not open_assets:
            open_assets = cataloged_assets

        return Response({
            'market_info': market_info,
            'open_assets_count': len(open_assets),
            'open_assets': open_assets[:10],  # First 10 assets
            'best_asset': best_asset,
            'recommendations': {
                'forex_trading': market_info.get('forex_open', False),
                'stock_trading': market_info.get('us_stocks_open', False),
                'binary_trading': binary_open,
                'weekend_mode': market_info.get('is_weekend', False)
            }
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter status do mercado: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def get_payouts(request):
    """Return payouts for a given list of assets.
    Body: { assets: ["EURUSD", ...], account_type?: "PRACTICE"|"REAL" }
    """
    try:
        data = request.data or {}
        assets = data.get('assets') or []
        if not isinstance(assets, list) or not assets:
            return Response({'error': 'Informe a lista de ativos em "assets".'}, status=status.HTTP_400_BAD_REQUEST)

        # Limit the number of assets to avoid heavy calls
        assets = [str(a).upper() for a in assets][:50]

        account_type = data.get('account_type') or 'PRACTICE'

        api = IQOptionManager.get_instance(request.user)
        if not api:
            return Response({'error': 'Credenciais da IQ Option não configuradas.'}, status=status.HTTP_400_BAD_REQUEST)

        # IMPORTANT: Do NOT establish a new connection here.
        # If not connected, return fallback payouts to avoid implicit login/connect on dashboard load.
        if not api.connected:
            payouts = [{'asset': a, 'binary': 80, 'turbo': 0, 'digital': 80} for a in assets]
            return Response({'payouts': payouts, 'count': len(payouts), 'connected': False})

        # When already connected, ensure account type and fetch live payouts
        ok, msg = api.change_account(account_type)
        if not ok:
            return Response({'error': f'Falha ao trocar conta: {msg}'}, status=status.HTTP_400_BAD_REQUEST)

        payouts = []
        for a in assets:
            try:
                p = api.get_payout(a)
                payouts.append({'asset': a, **p})
            except Exception as e:
                payouts.append({'asset': a, 'binary': 80, 'turbo': 0, 'digital': 80, 'error': str(e)})

        return Response({'payouts': payouts, 'count': len(payouts), 'connected': True})

    except Exception as e:
        return Response({'error': f'Erro ao obter payouts: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_available_strategies(request):
    """Return list of all available trading strategies with their information"""
    try:
        strategies = get_strategy_info()
        return Response({
            'strategies': strategies,
            'count': len(strategies)
        })
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter estratégias: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================
# ADVANCED ANALYSIS ENDPOINTS
# ============================================

from .advanced_analysis import (
    SmartAssetSelector, MultiTimeframeAnalyzer, TrendAnalyzer,
    CorrelationManager, TradingScheduler, ConsecutiveLossTracker,
    AssetBlacklist, get_correlation_manager, get_loss_tracker, get_blacklist
)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_best_assets(request):
    """Get best assets to trade based on catalog and advanced analysis"""
    try:
        user = request.user
        
        # Get filter parameters from query or user config
        try:
            config = user.trading_config
            min_win_rate = float(request.query_params.get('min_win_rate', config.min_win_rate_filter))
            min_gale1_rate = float(request.query_params.get('min_gale1_rate', config.min_gale1_rate_filter))
            check_trend = request.query_params.get('check_trend', 'true').lower() == 'true'
            check_correlation = config.check_correlation
        except Exception:
            min_win_rate = float(request.query_params.get('min_win_rate', 60))
            min_gale1_rate = float(request.query_params.get('min_gale1_rate', 75))
            check_trend = request.query_params.get('check_trend', 'true').lower() == 'true'
            check_correlation = True
        
        max_results = int(request.query_params.get('max_results', 10))
        
        # Only main strategies (mhi, torres_gemeas, mhi_m5) - not confirmation filters
        main_strategies = ['mhi', 'torres_gemeas', 'mhi_m5']
        
        # Get catalog results - only main strategies
        catalog_results = AssetCatalog.objects.filter(
            user=user,
            strategy__in=main_strategies
        ).values(
            'asset', 'strategy', 'win_rate', 'gale1_rate', 'gale2_rate', 
            'gale3_rate', 'total_samples', 'analyzed_at', 'trend', 'score'
        )
        
        # Filter and sort
        filtered_results = []
        for result in catalog_results:
            win_rate = float(result['win_rate'])
            gale1_rate = float(result['gale1_rate'])
            
            if win_rate >= min_win_rate and gale1_rate >= min_gale1_rate:
                # Calculate score if not already set
                score = float(result.get('score', 0))
                if score == 0:
                    score = win_rate
                    if gale1_rate >= 80:
                        score += 10
                    if float(result['gale2_rate']) >= 90:
                        score += 5
                    if result['total_samples'] >= 30:
                        score += 5
                    elif result['total_samples'] < 10:
                        score -= 10
                
                filtered_results.append({
                    **result,
                    'score': round(score, 2),
                    'is_recommended': win_rate >= 60 and gale1_rate >= 75,
                    'analyzed_at': result['analyzed_at'].isoformat() if result['analyzed_at'] else None
                })
        
        # Sort by score
        filtered_results.sort(key=lambda x: x['score'], reverse=True)
        
        return Response({
            'assets': filtered_results[:max_results],
            'total_filtered': len(filtered_results),
            'filters': {
                'min_win_rate': min_win_rate,
                'min_gale1_rate': min_gale1_rate,
                'check_trend': check_trend,
                'check_correlation': check_correlation
            }
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter melhores ativos: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_multi_timeframe_analysis(request):
    """Get multi-timeframe analysis for an asset"""
    try:
        asset = request.query_params.get('asset')
        if not asset:
            return Response({'error': 'Parâmetro "asset" é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
        
        timeframes_param = request.query_params.get('timeframes', '60,300')
        timeframes = [int(tf.strip()) for tf in timeframes_param.split(',')]
        
        api = IQOptionManager.get_instance(request.user)
        if not api or not api.connected:
            return Response({'error': 'API não conectada'}, status=status.HTTP_400_BAD_REQUEST)
        
        analyzer = MultiTimeframeAnalyzer(api)
        result = analyzer.analyze_multi_timeframe(asset, timeframes)
        
        return Response(result)
        
    except Exception as e:
        return Response(
            {'error': f'Erro na análise multi-timeframe: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_trading_schedule(request):
    """Get current trading schedule and recommended assets"""
    try:
        current_sessions = TradingScheduler.get_current_session()
        recommended_assets = TradingScheduler.get_recommended_assets()
        
        # Check specific asset if provided
        asset = request.query_params.get('asset')
        asset_check = None
        if asset:
            is_good, reason = TradingScheduler.is_good_time_for_asset(asset)
            asset_check = {'asset': asset, 'is_good_time': is_good, 'reason': reason}
        
        return Response({
            'current_sessions': current_sessions,
            'recommended_assets': recommended_assets,
            'asset_check': asset_check,
            'sessions_info': TradingScheduler.TRADING_SESSIONS
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter schedule: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_correlation_status(request):
    """Get current correlation exposure status"""
    try:
        manager = get_correlation_manager(request.user.id)
        
        # Check specific asset if provided
        asset = request.query_params.get('asset')
        asset_check = None
        if asset:
            can_trade, reason = manager.can_trade_asset(asset)
            group = manager.get_correlation_group(asset)
            asset_check = {
                'asset': asset,
                'can_trade': can_trade,
                'reason': reason,
                'correlation_group': group
            }
        
        return Response({
            'active_correlations': manager.get_active_correlations(),
            'asset_check': asset_check
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter status de correlação: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_loss_tracker_status(request):
    """Get consecutive loss tracker status"""
    try:
        tracker = get_loss_tracker(request.user.id)
        return Response(tracker.get_status())
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter status de perdas: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def reset_loss_tracker(request):
    """Reset consecutive loss tracker"""
    try:
        tracker = get_loss_tracker(request.user.id)
        tracker.reset()
        return Response({'message': 'Contador de perdas resetado', 'status': tracker.get_status()})
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao resetar contador: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def manage_blacklist(request):
    """Manage asset blacklist"""
    try:
        blacklist = get_blacklist(request.user.id)
        
        if request.method == 'GET':
            return Response(blacklist.get_blacklist())
        
        elif request.method == 'POST':
            asset = request.data.get('asset')
            if not asset:
                return Response({'error': 'Parâmetro "asset" é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
            
            temporary = request.data.get('temporary', False)
            duration = int(request.data.get('duration_minutes', 60))
            
            blacklist.add_to_blacklist(asset, temporary=temporary, duration_minutes=duration)
            return Response({
                'message': f'Ativo {asset} adicionado à blacklist',
                'blacklist': blacklist.get_blacklist()
            })
        
        elif request.method == 'DELETE':
            asset = request.data.get('asset')
            if not asset:
                return Response({'error': 'Parâmetro "asset" é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
            
            blacklist.remove_from_blacklist(asset)
            return Response({
                'message': f'Ativo {asset} removido da blacklist',
                'blacklist': blacklist.get_blacklist()
            })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao gerenciar blacklist: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_strategy_performance(request):
    """Get performance statistics by strategy"""
    try:
        user = request.user
        days = int(request.query_params.get('days', 30))
        
        from_date = timezone.now() - timedelta(days=days)
        
        # Get operations grouped by strategy
        operations = Operation.objects.filter(
            session__user=user,
            created_at__gte=from_date
        ).values('session__strategy').annotate(
            total=Count('id'),
            wins=Count('id', filter=Q(result='WIN')),
            losses=Count('id', filter=Q(result='LOSS')),
            profit=Sum('profit_loss')
        )
        
        strategy_stats = []
        for op in operations:
            strategy = op['session__strategy']
            total = op['total']
            wins = op['wins']
            win_rate = (wins / total * 100) if total > 0 else 0
            
            strategy_stats.append({
                'strategy': strategy,
                'total_operations': total,
                'wins': wins,
                'losses': op['losses'],
                'win_rate': round(win_rate, 2),
                'profit_loss': float(op['profit'] or 0)
            })
        
        # Sort by win rate
        strategy_stats.sort(key=lambda x: x['win_rate'], reverse=True)
        
        return Response({
            'strategies': strategy_stats,
            'period_days': days,
            'best_strategy': strategy_stats[0]['strategy'] if strategy_stats else None
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter performance: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_daily_performance(request):
    """Get daily performance statistics"""
    try:
        user = request.user
        days = int(request.query_params.get('days', 7))
        
        daily_stats = []
        
        for i in range(days):
            date = timezone.now().date() - timedelta(days=i)
            start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
            
            operations = Operation.objects.filter(
                session__user=user,
                created_at__gte=start,
                created_at__lte=end
            )
            
            total = operations.count()
            wins = operations.filter(result='WIN').count()
            profit = operations.aggregate(total=Sum('profit_loss'))['total'] or 0
            
            daily_stats.append({
                'date': date.isoformat(),
                'total_operations': total,
                'wins': wins,
                'losses': operations.filter(result='LOSS').count(),
                'win_rate': round((wins / total * 100) if total > 0 else 0, 2),
                'profit_loss': float(profit)
            })
        
        return Response({
            'daily_stats': daily_stats,
            'period_days': days
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter performance diária: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_catalog_with_filters(request):
    """Get catalog results with advanced filters"""
    try:
        user = request.user
        
        # Get filter parameters
        min_win_rate = float(request.query_params.get('min_win_rate', 0))
        min_gale1_rate = float(request.query_params.get('min_gale1_rate', 0))
        min_samples = int(request.query_params.get('min_samples', 0))
        strategy = request.query_params.get('strategy')
        trend = request.query_params.get('trend')
        sort_by = request.query_params.get('sort_by', 'score')
        order = request.query_params.get('order', 'desc')
        
        # Build query
        queryset = AssetCatalog.objects.filter(user=user)
        
        if min_win_rate > 0:
            queryset = queryset.filter(win_rate__gte=min_win_rate)
        if min_gale1_rate > 0:
            queryset = queryset.filter(gale1_rate__gte=min_gale1_rate)
        if min_samples > 0:
            queryset = queryset.filter(total_samples__gte=min_samples)
        if strategy:
            queryset = queryset.filter(strategy=strategy)
        if trend:
            queryset = queryset.filter(trend=trend)
        
        # Sort
        order_prefix = '-' if order == 'desc' else ''
        valid_sort_fields = ['score', 'win_rate', 'gale1_rate', 'total_samples', 'analyzed_at']
        if sort_by in valid_sort_fields:
            queryset = queryset.order_by(f'{order_prefix}{sort_by}')
        
        # Serialize
        results = list(queryset.values(
            'asset', 'strategy', 'win_rate', 'gale1_rate', 'gale2_rate',
            'gale3_rate', 'total_samples', 'trend', 'trend_strength', 
            'score', 'payout', 'analyzed_at'
        ))
        
        # Format dates
        for r in results:
            if r['analyzed_at']:
                r['analyzed_at'] = r['analyzed_at'].isoformat()
        
        return Response({
            'results': results,
            'total': len(results),
            'filters': {
                'min_win_rate': min_win_rate,
                'min_gale1_rate': min_gale1_rate,
                'min_samples': min_samples,
                'strategy': strategy,
                'trend': trend,
                'sort_by': sort_by,
                'order': order
            }
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter catálogo: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
