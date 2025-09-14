from rest_framework import serializers
from .models import TradingSession, Operation, AssetCatalog, TradingLog, MarketData


class TradingSessionSerializer(serializers.ModelSerializer):
    """Serializer for trading sessions"""
    
    win_rate = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = TradingSession
        fields = [
            'id', 'status', 'strategy', 'asset', 'account_type',
            'initial_balance', 'current_balance', 'total_profit',
            'total_operations', 'wins', 'losses', 'draws', 'win_rate',
            'started_at', 'stopped_at', 'updated_at', 'is_active'
        ]
        read_only_fields = [
            'id', 'initial_balance', 'current_balance', 'total_profit',
            'total_operations', 'wins', 'losses', 'draws',
            'started_at', 'stopped_at', 'updated_at'
        ]


class OperationSerializer(serializers.ModelSerializer):
    """Serializer for trading operations, exposing aliases expected by the frontend."""
    
    # Aliases and normalized fields
    amount = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()
    strategy_used = serializers.SerializerMethodField()
    martingale_level = serializers.SerializerMethodField()
    soros_level = serializers.SerializerMethodField()
    session = serializers.SerializerMethodField()
    entry_price = serializers.SerializerMethodField()
    profit_loss = serializers.SerializerMethodField()
    
    class Meta:
        model = Operation
        fields = [
            # Original fields
            'id', 'asset', 'expiration_time', 'operation_type', 'profit_loss', 'created_at', 'closed_at',
            # Aliases / normalized
            'amount', 'entry_price', 'direction', 'result', 'strategy_used', 'martingale_level', 'soros_level', 'session',
        ]
        read_only_fields = ['id', 'created_at', 'closed_at']
    
    def get_amount(self, obj):
        try:
            return float(obj.entry_value)
        except Exception:
            return 0.0
    
    def get_entry_price(self, obj):
        try:
            return float(obj.entry_value)
        except Exception:
            return 0.0
    
    def get_direction(self, obj):
        try:
            return (obj.direction or '').lower()
        except Exception:
            return None
    
    def get_result(self, obj):
        try:
            r = (obj.result or '').lower()
            return r if r in ['win', 'loss', 'draw', 'pending'] else None
        except Exception:
            return None
    
    def get_strategy_used(self, obj):
        try:
            return obj.session.strategy
        except Exception:
            return None
    
    def get_martingale_level(self, obj):
        try:
            mapping = {
                'ENTRY': 0,
                'GALE1': 1,
                'GALE2': 2,
                'GALE3': 3,
            }
            return mapping.get(str(obj.operation_type).upper(), 0)
        except Exception:
            return 0
    
    def get_soros_level(self, obj):
        # Soros level not tracked per operation; expose 0 for now
        return 0
    
    def get_session(self, obj):
        try:
            # return UUID as string
            return str(obj.session_id)
        except Exception:
            return None

    def get_profit_loss(self, obj):
        try:
            return float(obj.profit_loss)
        except Exception:
            return 0.0


class AssetCatalogSerializer(serializers.ModelSerializer):
    """Serializer for asset catalog"""
    
    class Meta:
        model = AssetCatalog
        fields = [
            'asset', 'strategy', 'win_rate', 'gale1_rate', 'gale2_rate', 'gale3_rate',
            'total_samples', 'analyzed_at'
        ]
        read_only_fields = ['analyzed_at']


class TradingLogSerializer(serializers.ModelSerializer):
    """Serializer for trading logs"""
    
    class Meta:
        model = TradingLog
        fields = ['id', 'level', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']


class MarketDataSerializer(serializers.ModelSerializer):
    """Serializer for market data"""
    
    is_green = serializers.ReadOnlyField()
    is_red = serializers.ReadOnlyField()
    is_doji = serializers.ReadOnlyField()
    
    class Meta:
        model = MarketData
        fields = [
            'asset', 'timeframe', 'open_price', 'high_price',
            'low_price', 'close_price', 'volume', 'timestamp',
            'is_green', 'is_red', 'is_doji'
        ]
        read_only_fields = ['timestamp']


class StartTradingSerializer(serializers.Serializer):
    """Serializer for starting trading session"""
    
    strategy = serializers.ChoiceField(
        choices=[
            ('mhi', 'MHI'),
            ('torres_gemeas', 'Torres Gêmeas'),
            ('mhi_m5', 'MHI M5')
        ]
    )
    asset = serializers.CharField(max_length=20)
    account_type = serializers.ChoiceField(
        choices=[('PRACTICE', 'Demo'), ('REAL', 'Real')],
        default='PRACTICE'
    )
    
    def validate_asset(self, value):
        if not value or len(value) < 3:
            raise serializers.ValidationError("Ativo inválido.")
        return value.upper()


class StopTradingSerializer(serializers.Serializer):
    """Serializer for stopping trading session"""
    
    session_id = serializers.UUIDField()


class CatalogAssetsSerializer(serializers.Serializer):
    """Serializer for asset cataloging request"""
    
    account_type = serializers.ChoiceField(
        choices=[('PRACTICE', 'Demo'), ('REAL', 'Real')],
        default='PRACTICE'
    )
    
    strategies = serializers.MultipleChoiceField(
        choices=[
            ('mhi', 'MHI'),
            ('torres_gemeas', 'Torres Gêmeas'),
            ('mhi_m5', 'MHI M5')
        ],
        default=['mhi', 'torres_gemeas', 'mhi_m5']
    )


class SessionStatsSerializer(serializers.Serializer):
    """Serializer for session statistics"""
    
    total_sessions = serializers.IntegerField()
    active_sessions = serializers.IntegerField()
    total_profit = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_operations = serializers.IntegerField()
    overall_win_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    best_strategy = serializers.CharField()
    best_asset = serializers.CharField()


class DashboardDataSerializer(serializers.Serializer):
    """Serializer for dashboard data"""
    
    current_session = TradingSessionSerializer(allow_null=True)
    recent_operations = OperationSerializer(many=True)
    session_stats = SessionStatsSerializer()
    recent_logs = TradingLogSerializer(many=True)
    account_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    connection_status = serializers.BooleanField()
