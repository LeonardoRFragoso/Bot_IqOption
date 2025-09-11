from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
import threading
import time

from .models import TradingSession, Operation, AssetCatalog, TradingLog, MarketData
from .serializers import (
    TradingSessionSerializer, OperationSerializer, AssetCatalogSerializer,
    TradingLogSerializer, StartTradingSerializer, StopTradingSerializer,
    CatalogAssetsSerializer, DashboardDataSerializer, SessionStatsSerializer
)
from .iq_api import IQOptionManager
from .strategies import get_strategy
from .catalog import AssetCatalogService


# Global dictionary to store running trading threads
trading_threads = {}


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
@permission_classes([permissions.IsAuthenticated])
def start_trading(request):
    """Start a new trading session"""
    
    serializer = StartTradingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    
    # Check if user already has an active session
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
    
    def run_trading():
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
            
            # Remove from active threads
            if session.id in trading_threads:
                del trading_threads[session.id]
    
    thread = threading.Thread(target=run_trading)
    thread.daemon = True
    thread.start()
    
    # Store thread reference
    trading_threads[session.id] = {
        'thread': thread,
        'strategy': strategy,
        'api': api
    }
    
    return Response(TradingSessionSerializer(session).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
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
@permission_classes([permissions.IsAuthenticated])
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
        
        thread = threading.Thread(
            target=run_trading,
            args=(strategy, session.asset)
        )
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
@permission_classes([permissions.IsAuthenticated])
def stop_trading(request):
    """Stop active trading session"""
    
    serializer = StopTradingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    session_id = serializer.validated_data['session_id']
    session = get_object_or_404(
        TradingSession,
        id=session_id,
        user=request.user,
        status__in=['RUNNING', 'PAUSED']
    )
    
    # Stop strategy if running
    if session_id in trading_threads:
        thread_info = trading_threads[session_id]
        strategy = thread_info['strategy']
        strategy.stop()
        
        # Wait for thread to finish (max 10 seconds)
        thread_info['thread'].join(timeout=10)
        
        del trading_threads[session_id]
    
    # Update session status
    session.status = 'STOPPED'
    session.stopped_at = timezone.now()
    session.save()
    
    return Response({'message': 'Sessão de trading parada com sucesso.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_active_session(request):
    """Get user's active trading session"""
    
    session = TradingSession.objects.filter(
        user=request.user,
        status__in=['RUNNING', 'PAUSED']
    ).first()
    
    if session:
        return Response(TradingSessionSerializer(session).data)
    else:
        return Response({'session': None})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def catalog_assets(request):
    """Catalog assets for strategies"""
    
    serializer = CatalogAssetsSerializer(data=request.data)
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
    
    thread = threading.Thread(target=run_cataloging)
    thread.daemon = True
    thread.start()
    
    return Response({'message': 'Catalogação iniciada. Verifique os logs para acompanhar o progresso.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_catalog_results(request):
    """Get asset catalog results"""
    
    catalogs = AssetCatalog.objects.filter(user=request.user).order_by('-win_rate')
    serializer = AssetCatalogSerializer(catalogs, many=True)
    
    return Response(serializer.data)


class OperationListView(generics.ListAPIView):
    """List user's trading operations"""
    
    serializer_class = OperationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Operation.objects.filter(
            session__user=self.request.user
        ).order_by('-created_at')


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
    
    # Recent operations (last 20)
    recent_operations = Operation.objects.filter(
        session__user=user
    ).order_by('-created_at')[:20]
    
    # Session statistics
    sessions = TradingSession.objects.filter(user=user)
    total_sessions = sessions.count()
    active_sessions = sessions.filter(status__in=['RUNNING', 'PAUSED']).count()
    
    # Financial statistics
    total_profit = sessions.aggregate(
        total=Sum('total_profit')
    )['total'] or 0
    
    total_operations = sessions.aggregate(
        total=Sum('total_operations')
    )['total'] or 0
    
    total_wins = sessions.aggregate(
        total=Sum('wins')
    )['total'] or 0
    
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
    
    dashboard_data = {
        'current_session': TradingSessionSerializer(current_session).data if current_session else None,
        'recent_operations': OperationSerializer(recent_operations, many=True).data,
        'session_stats': session_stats,
        'recent_logs': TradingLogSerializer(recent_logs, many=True).data,
        'account_balance': account_balance,
        'connection_status': connection_status
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
        
        if not api:
            return Response(
                {'error': 'Credenciais da IQ Option não configuradas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get market status info
        market_info = api.get_market_status_info()
        
        # Get available assets
        open_assets = api.get_open_assets()
        
        # Get best available asset
        best_asset = api.get_best_available_asset()
        
        return Response({
            'market_info': market_info,
            'open_assets_count': len(open_assets),
            'open_assets': open_assets[:10],  # First 10 assets
            'best_asset': best_asset,
            'recommendations': {
                'forex_trading': market_info.get('forex_open', False),
                'stock_trading': market_info.get('us_stocks_open', False),
                'weekend_mode': market_info.get('is_weekend', False)
            }
        })
        
    except Exception as e:
        return Response(
            {'error': f'Erro ao obter status do mercado: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
