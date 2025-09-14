from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, TradingConfiguration


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model"""
    
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_active_trader', 'preferred_account_type', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'is_active_trader', 'preferred_account_type', 'created_at')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('IQ Option', {
            'fields': ('preferred_account_type', 'is_active_trader')
        }),
        ('Informações Adicionais', {
            'fields': ('phone', 'created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'iq_email', 'iq_password')
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Informações Pessoais', {
            'fields': ('email', 'first_name', 'last_name', 'phone')
        }),
    )


@admin.register(TradingConfiguration)
class TradingConfigurationAdmin(admin.ModelAdmin):
    """Admin configuration for TradingConfiguration model"""
    
    list_display = ('user', 'valor_entrada', 'stop_win', 'stop_loss', 'tipo', 'martingale_usar', 'soros_usar', 'default_strategy', 'updated_at')
    list_filter = ('tipo', 'martingale_usar', 'soros_usar', 'analise_medias', 'tipo_par', 'default_strategy', 'torres_event_driven', 'updated_at')
    search_fields = ('user__email', 'user__username')
    ordering = ('-updated_at',)
    
    fieldsets = (
        ('Usuário', {
            'fields': ('user',)
        }),
        ('Configurações Gerais [AJUSTES]', {
            'fields': ('tipo', 'valor_entrada', 'tipo_par', 'default_strategy')
        }),
        ('Stop Loss/Win', {
            'fields': ('stop_win', 'stop_loss')
        }),
        ('Análise de Médias', {
            'fields': ('analise_medias', 'velas_medias')
        }),
        ('Martingale', {
            'fields': ('martingale_usar', 'martingale_niveis', 'martingale_fator')
        }),
        ('Soros', {
            'fields': ('soros_usar', 'soros_niveis')
        }),
        ('Torres Gêmeas', {
            'fields': (
                'torres_event_driven', 'torres_event_cooldown_sec',
                'torres_timeframe', 'torres_lookback',
                'torres_tolerancia_pct', 'torres_break_buffer_pct',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
