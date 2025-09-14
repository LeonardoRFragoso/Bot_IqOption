from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import EmailValidator
from cryptography.fernet import Fernet
from django.conf import settings
import os


class User(AbstractUser):
    """Custom User model with additional fields for IQ Option integration"""
    
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text="Email usado para login no sistema"
    )
    
    # IQ Option credentials (encrypted)
    iq_email = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Email da conta IQ Option (criptografado)"
    )
    
    iq_password = models.TextField(
        blank=True,
        null=True,
        help_text="Senha da conta IQ Option (criptografada)"
    )
    
    # Trading preferences
    preferred_account_type = models.CharField(
        max_length=10,
        choices=[
            ('PRACTICE', 'Demo'),
            ('REAL', 'Real')
        ],
        default='PRACTICE',
        help_text="Tipo de conta preferido para trading"
    )
    
    # Profile info
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active_trader = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
    
    def __str__(self):
        return f"{self.email} ({self.username})"
    
    @property
    def encryption_key(self):
        """Get or create encryption key for this user"""
        key_file = f"user_{self.id}_key.key"
        key_path = os.path.join(settings.BASE_DIR, 'keys', key_file)
        
        if not os.path.exists(os.path.dirname(key_path)):
            os.makedirs(os.path.dirname(key_path))
        
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_path, 'wb') as f:
                f.write(key)
            return key
    
    def set_iq_credentials(self, email, password):
        """Encrypt and store IQ Option credentials"""
        if email and password:
            fernet = Fernet(self.encryption_key)
            self.iq_email = fernet.encrypt(email.encode()).decode()
            self.iq_password = fernet.encrypt(password.encode()).decode()
            self.save()
    
    def get_iq_credentials(self):
        """Decrypt and return IQ Option credentials"""
        if self.iq_email and self.iq_password:
            try:
                fernet = Fernet(self.encryption_key)
                email = fernet.decrypt(self.iq_email.encode()).decode()
                password = fernet.decrypt(self.iq_password.encode()).decode()
                return email, password
            except Exception:
                return None, None
        return None, None


class Notification(models.Model):
    """User notifications model"""
    
    TYPE_CHOICES = [
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('info', 'Info'),
    ]
    
    CATEGORY_CHOICES = [
        ('trading', 'Trading'),
        ('system', 'System'),
        ('account', 'Account'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='info')
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='system')
    title = models.CharField(max_length=200)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_notifications'
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"


class TradingConfiguration(models.Model):
    """Trading configuration for each user - based on config.txt structure"""
    
    OPERATION_TYPE_CHOICES = [
        ('automatico', 'Automático'),
        ('manual', 'Manual'),
    ]
    
    PAIR_TYPE_CHOICES = [
        ('automatico', 'Automático (Todos os Pares)'),
        ('manual', 'Manual'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='trading_config'
    )
    
    # [AJUSTES] section from config.txt
    tipo = models.CharField(
        max_length=20, 
        choices=OPERATION_TYPE_CHOICES, 
        default='automatico',
        help_text="Tipo de operação"
    )
    valor_entrada = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=3.00,
        help_text="Valor de entrada"
    )
    stop_win = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50.00,
        help_text="Stop Win"
    )
    stop_loss = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=70.00,
        help_text="Stop Loss"
    )
    analise_medias = models.BooleanField(
        default=False,
        help_text="Análise de médias (N=False, S=True)"
    )
    velas_medias = models.IntegerField(
        default=3,
        help_text="Número de velas para análise de médias"
    )
    tipo_par = models.CharField(
        max_length=30,
        choices=PAIR_TYPE_CHOICES,
        default='automatico',
        help_text="Tipo de par para trading"
    )
    
    # [MARTINGALE] section from config.txt
    martingale_usar = models.BooleanField(
        default=True,
        help_text="Usar Martingale (S=True, N=False)"
    )
    martingale_niveis = models.IntegerField(
        default=1,
        help_text="Níveis do Martingale"
    )
    martingale_fator = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text="Fator multiplicador do Martingale"
    )
    
    # [SOROS] section from config.txt
    soros_usar = models.BooleanField(
        default=True,
        help_text="Usar Soros (S=True, N=False)"
    )
    soros_niveis = models.IntegerField(
        default=1,
        help_text="Níveis do Soros"
    )
    
    # Additional fields for strategy selection
    default_strategy = models.CharField(
        max_length=20,
        choices=[
            ('mhi', 'MHI'),
            ('torres_gemeas', 'Torres Gêmeas'),
            ('mhi_m5', 'MHI M5'),
        ],
        default='mhi',
        help_text="Estratégia padrão"
    )
    
    # Parâmetros específicos da estratégia Torres Gêmeas
    torres_event_driven = models.BooleanField(
        default=False,
        help_text="Acionar por rompimento (sem gate de minuto)"
    )
    torres_event_cooldown_sec = models.IntegerField(
        default=45,
        help_text="Cooldown entre sinais event-driven (s)"
    )
    torres_timeframe = models.IntegerField(
        default=60,
        help_text="Timeframe em segundos (padrão M1=60)"
    )
    torres_lookback = models.IntegerField(
        default=60,
        help_text="Número de velas para detectar A-B-C"
    )
    torres_tolerancia_pct = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.050,
        help_text="Tolerância de similaridade das torres em %"
    )
    torres_break_buffer_pct = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.000,
        help_text="Buffer extra para confirmar rompimento em %"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_trading_configuration'
        verbose_name = 'Configuração de Trading'
        verbose_name_plural = 'Configurações de Trading'
    
    def __str__(self):
        return f"Config - {self.user.email}"
    
    def to_legacy_format(self):
        """Convert to legacy config.txt format for compatibility"""
        email, password = self.user.get_iq_credentials()
        return {
            'LOGIN': {
                'email': email or 'example@email.com',
                'senha': password or 'sua_senha',
            },
            'AJUSTES': {
                'tipo': self.tipo,
                'valor_entrada': float(self.valor_entrada),
                'stop_win': float(self.stop_win),
                'stop_loss': float(self.stop_loss),
                'analise_medias': 'S' if self.analise_medias else 'N',
                'velas_medias': self.velas_medias,
                'tipo_par': self.get_tipo_par_display(),
            },
            'MARTINGALE': {
                'usar': 'S' if self.martingale_usar else 'N',
                'niveis': self.martingale_niveis,
                'fator': float(self.martingale_fator),
            },
            'SOROS': {
                'usar': 'S' if self.soros_usar else 'N',
                'niveis': self.soros_niveis,
            }
        }
