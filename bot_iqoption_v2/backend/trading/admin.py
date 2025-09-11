from django.contrib import admin
from .models import TradingSession, Operation, AssetCatalog, TradingLog, MarketData


@admin.register(TradingSession)
class TradingSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user', 'strategy', 'asset', 'account_type', 'status',
        'total_operations', 'wins', 'losses', 'total_profit', 'started_at'
    ]
    list_filter = ['strategy', 'asset', 'account_type', 'status', 'started_at']
    search_fields = ['user__email', 'asset']
    readonly_fields = ['id', 'started_at', 'updated_at']
    ordering = ['-started_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('id', 'user', 'strategy', 'asset', 'account_type', 'status')
        }),
        ('Balanços', {
            'fields': ('initial_balance', 'current_balance', 'total_profit')
        }),
        ('Estatísticas', {
            'fields': ('total_operations', 'wins', 'losses', 'draws')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'stopped_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session', 'asset', 'direction', 'entry_value', 'result',
        'profit_loss', 'operation_type', 'created_at'
    ]
    list_filter = ['direction', 'result', 'operation_type', 'created_at']
    search_fields = ['session__user__email', 'asset', 'iq_order_id']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Informações da Operação', {
            'fields': ('id', 'session', 'iq_order_id', 'asset', 'direction')
        }),
        ('Valores', {
            'fields': ('entry_value', 'expiration_time', 'profit_loss')
        }),
        ('Resultado', {
            'fields': ('result', 'operation_type')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'closed_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(AssetCatalog)
class AssetCatalogAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'asset', 'strategy', 'win_rate', 'gale1_rate',
        'gale2_rate', 'total_samples', 'analyzed_at'
    ]
    list_filter = ['strategy', 'asset', 'analyzed_at']
    search_fields = ['user__email', 'asset']
    readonly_fields = ['analyzed_at']
    ordering = ['-gale2_rate', '-win_rate']
    
    fieldsets = (
        ('Informações', {
            'fields': ('user', 'asset', 'strategy')
        }),
        ('Estatísticas', {
            'fields': ('win_rate', 'gale1_rate', 'gale2_rate', 'total_samples')
        }),
        ('Timestamps', {
            'fields': ('analyzed_at',),
            'classes': ('collapse',)
        })
    )


@admin.register(TradingLog)
class TradingLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'session', 'level', 'message_preview', 'created_at']
    list_filter = ['level', 'created_at']
    search_fields = ['user__email', 'message']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    def message_preview(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message Preview'
    
    fieldsets = (
        ('Log Info', {
            'fields': ('user', 'session', 'level')
        }),
        ('Content', {
            'fields': ('message',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )


@admin.register(MarketData)
class MarketDataAdmin(admin.ModelAdmin):
    list_display = ['asset', 'timeframe', 'timestamp', 'open_price', 'close_price', 'volume']
    list_filter = ['asset', 'timeframe', 'timestamp']
    search_fields = ['asset']
    readonly_fields = ['created_at']
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Market Info', {
            'fields': ('asset', 'timeframe', 'timestamp')
        }),
        ('OHLC Data', {
            'fields': ('open_price', 'high_price', 'low_price', 'close_price')
        }),
        ('Volume', {
            'fields': ('volume',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
