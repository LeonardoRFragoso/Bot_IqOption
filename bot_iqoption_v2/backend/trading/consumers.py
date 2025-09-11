import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import TradingSession, Operation, TradingLog

User = get_user_model()


class TradingConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time trading updates"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.user_group_name = f"trading_{self.user.id}"
        
        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            # Leave user group
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'get_status':
                await self.send_status_update()
            elif message_type == 'get_logs':
                await self.send_recent_logs()
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
    
    async def send_initial_data(self):
        """Send initial data when client connects"""
        await self.send_status_update()
        await self.send_recent_logs()
    
    async def send_status_update(self):
        """Send current trading status"""
        session_data = await self.get_active_session()
        recent_operations = await self.get_recent_operations()
        
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'data': {
                'active_session': session_data,
                'recent_operations': recent_operations
            }
        }))
    
    async def send_recent_logs(self):
        """Send recent trading logs"""
        logs = await self.get_recent_logs()
        
        await self.send(text_data=json.dumps({
            'type': 'logs_update',
            'data': {
                'logs': logs
            }
        }))
    
    @database_sync_to_async
    def get_active_session(self):
        """Get user's active trading session"""
        try:
            session = TradingSession.objects.filter(
                user=self.user,
                status__in=['RUNNING', 'PAUSED']
            ).first()
            
            if session:
                return {
                    'id': str(session.id),
                    'strategy': session.strategy,
                    'asset': session.asset,
                    'status': session.status,
                    'total_operations': session.total_operations,
                    'wins': session.wins,
                    'losses': session.losses,
                    'total_profit': float(session.total_profit),
                    'current_balance': float(session.current_balance),
                    'created_at': session.created_at.isoformat()
                }
            return None
        except Exception:
            return None
    
    @database_sync_to_async
    def get_recent_operations(self):
        """Get recent trading operations"""
        try:
            operations = Operation.objects.filter(
                session__user=self.user
            ).order_by('-created_at')[:10]
            
            return [{
                'id': str(op.id),
                'asset': op.asset,
                'direction': op.direction,
                'amount': float(op.amount),
                'result': op.result,
                'profit_loss': float(op.profit_loss) if op.profit_loss else 0,
                'martingale_level': op.martingale_level,
                'created_at': op.created_at.isoformat()
            } for op in operations]
        except Exception:
            return []
    
    @database_sync_to_async
    def get_recent_logs(self):
        """Get recent trading logs"""
        try:
            logs = TradingLog.objects.filter(
                user=self.user
            ).order_by('-created_at')[:20]
            
            return [{
                'id': str(log.id),
                'level': log.level,
                'message': log.message,
                'created_at': log.created_at.isoformat()
            } for log in logs]
        except Exception:
            return []
    
    # Group message handlers
    async def trading_update(self, event):
        """Handle trading update from group"""
        await self.send(text_data=json.dumps({
            'type': 'trading_update',
            'data': event['data']
        }))
    
    async def operation_update(self, event):
        """Handle operation update from group"""
        await self.send(text_data=json.dumps({
            'type': 'operation_update',
            'data': event['data']
        }))
    
    async def log_update(self, event):
        """Handle log update from group"""
        await self.send(text_data=json.dumps({
            'type': 'log_update',
            'data': event['data']
        }))
    
    async def session_update(self, event):
        """Handle session update from group"""
        await self.send(text_data=json.dumps({
            'type': 'session_update',
            'data': event['data']
        }))


class MonitoringConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for general monitoring updates"""
    
    async def connect(self):
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.monitoring_group_name = f"monitoring_{self.user.id}"
        
        # Join monitoring group
        await self.channel_layer.group_add(
            self.monitoring_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'monitoring_group_name'):
            # Leave monitoring group
            await self.channel_layer.group_discard(
                self.monitoring_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'subscribe_to_asset':
                asset = text_data_json.get('asset')
                if asset:
                    await self.subscribe_to_asset(asset)
            elif message_type == 'unsubscribe_from_asset':
                asset = text_data_json.get('asset')
                if asset:
                    await self.unsubscribe_from_asset(asset)
                    
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
    
    async def subscribe_to_asset(self, asset):
        """Subscribe to asset price updates"""
        asset_group_name = f"asset_{asset}"
        
        await self.channel_layer.group_add(
            asset_group_name,
            self.channel_name
        )
        
        await self.send(text_data=json.dumps({
            'type': 'subscription_confirmed',
            'asset': asset
        }))
    
    async def unsubscribe_from_asset(self, asset):
        """Unsubscribe from asset price updates"""
        asset_group_name = f"asset_{asset}"
        
        await self.channel_layer.group_discard(
            asset_group_name,
            self.channel_name
        )
        
        await self.send(text_data=json.dumps({
            'type': 'unsubscription_confirmed',
            'asset': asset
        }))
    
    # Group message handlers
    async def price_update(self, event):
        """Handle price update from group"""
        await self.send(text_data=json.dumps({
            'type': 'price_update',
            'data': event['data']
        }))
    
    async def market_update(self, event):
        """Handle market update from group"""
        await self.send(text_data=json.dumps({
            'type': 'market_update',
            'data': event['data']
        }))
