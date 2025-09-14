from django.db import models
from django.conf import settings
from decimal import Decimal
import uuid


class TradingSession(models.Model):
    """Model to track trading sessions"""
    
    STATUS_CHOICES = [
        ('STOPPED', 'Parado'),
        ('RUNNING', 'Executando'),
        ('PAUSED', 'Pausado'),
        ('ERROR', 'Erro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trading_sessions')
    
    # Session info
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='STOPPED')
    strategy = models.CharField(max_length=50, help_text="Estratégia utilizada")
    asset = models.CharField(max_length=20, help_text="Ativo negociado")
    account_type = models.CharField(
        max_length=10,
        choices=[('PRACTICE', 'Demo'), ('REAL', 'Real')],
        default='PRACTICE'
    )
    
    # Financial tracking
    initial_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Session statistics
    total_operations = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'trading_session'
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Sessão {self.id} - {self.user.email} - {self.strategy}"
    
    @property
    def win_rate(self):
        """Calculate win rate percentage"""
        if self.total_operations == 0:
            return 0
        return round((self.wins / self.total_operations) * 100, 2)
    
    @property
    def is_active(self):
        """Check if session is currently active"""
        return self.status in ['RUNNING', 'PAUSED']


class Operation(models.Model):
    """Model to track individual trading operations"""
    
    DIRECTION_CHOICES = [
        ('CALL', 'Call'),
        ('PUT', 'Put'),
    ]
    
    RESULT_CHOICES = [
        ('WIN', 'Vitória'),
        ('LOSS', 'Derrota'),
        ('DRAW', 'Empate'),
        ('PENDING', 'Pendente'),
    ]
    
    OPERATION_TYPE_CHOICES = [
        ('ENTRY', 'Entrada'),
        ('GALE1', 'Gale 1'),
        ('GALE2', 'Gale 2'),
        ('GALE3', 'Gale 3'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TradingSession, on_delete=models.CASCADE, related_name='operations')
    
    # Operation details
    asset = models.CharField(max_length=20)
    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES)
    entry_value = models.DecimalField(max_digits=10, decimal_places=2)
    expiration_time = models.IntegerField(help_text="Tempo de expiração em minutos")
    
    # Operation type (entry, gale1, gale2, etc.)
    operation_type = models.CharField(max_length=10, choices=OPERATION_TYPE_CHOICES, default='ENTRY')
    
    # Results
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, default='PENDING')
    profit_loss = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # IQ Option specific
    iq_order_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'trading_operation'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Op {self.asset} {self.direction} - {self.result}"


class AssetCatalog(models.Model):
    """Model to store asset analysis results"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asset_catalogs')
    
    # Asset info
    asset = models.CharField(max_length=20)
    strategy = models.CharField(max_length=50)
    
    # Analysis results
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gale1_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gale2_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gale3_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Sample size
    total_samples = models.IntegerField(default=0)
    
    # Timestamps
    analyzed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'trading_asset_catalog'
        unique_together = ['user', 'asset', 'strategy']
        ordering = ['-win_rate']
    
    def __str__(self):
        return f"{self.asset} - {self.strategy} - {self.win_rate}%"


class MarketData(models.Model):
    """Model to store market data for analysis"""
    
    asset = models.CharField(max_length=20)
    timeframe = models.IntegerField(help_text="Timeframe em segundos")
    
    # OHLC data
    open_price = models.DecimalField(max_digits=15, decimal_places=8)
    high_price = models.DecimalField(max_digits=15, decimal_places=8)
    low_price = models.DecimalField(max_digits=15, decimal_places=8)
    close_price = models.DecimalField(max_digits=15, decimal_places=8)
    
    # Volume
    volume = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    
    # Timestamp
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'trading_market_data'
        unique_together = ['asset', 'timeframe', 'timestamp']
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.asset} - {self.timestamp}"
    
    @property
    def is_green(self):
        """Check if candle is green (bullish)"""
        return self.close_price > self.open_price
    
    @property
    def is_red(self):
        """Check if candle is red (bearish)"""
        return self.close_price < self.open_price
    
    @property
    def is_doji(self):
        """Check if candle is doji"""
        return self.close_price == self.open_price


class TradingLog(models.Model):
    """Model to store trading logs"""
    
    LOG_LEVELS = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
    ]
    
    session = models.ForeignKey(
        TradingSession, 
        on_delete=models.CASCADE, 
        related_name='logs',
        null=True, 
        blank=True
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trading_logs')
    
    level = models.CharField(max_length=10, choices=LOG_LEVELS, default='INFO')
    message = models.TextField()
    
    # Additional context
    operation = models.ForeignKey(
        Operation, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='logs'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'trading_log'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"[{self.level}] {self.message[:50]}..."
