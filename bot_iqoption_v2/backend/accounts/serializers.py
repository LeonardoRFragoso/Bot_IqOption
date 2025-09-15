from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, TradingConfiguration, Notification


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = (
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'phone'
        )
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("As senhas não coincidem.")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        
        # Create default trading configuration
        TradingConfiguration.objects.create(user=user)
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError('Credenciais inválidas.')
            if not user.is_active:
                raise serializers.ValidationError('Conta desativada.')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Email e senha são obrigatórios.')
        
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'preferred_account_type', 'is_active_trader',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class IQOptionCredentialsSerializer(serializers.Serializer):
    """Serializer for IQ Option credentials"""
    
    iq_email = serializers.EmailField()
    iq_password = serializers.CharField()
    
    def validate_iq_email(self, value):
        if not value:
            raise serializers.ValidationError("Email da IQ Option é obrigatório.")
        return value
    
    def validate_iq_password(self, value):
        if not value or len(value) < 6:
            raise serializers.ValidationError("Senha deve ter pelo menos 6 caracteres.")
        return value


class TradingConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for trading configuration"""
    
    class Meta:
        model = TradingConfiguration
        fields = (
            'id', 'tipo', 'valor_entrada', 'stop_win', 'stop_loss', 
            'analise_medias', 'velas_medias', 'tipo_par',
            'martingale_usar', 'martingale_niveis', 'martingale_fator',
            'soros_usar', 'soros_niveis', 'default_strategy',
            # Filtros ativos e parâmetros
            'filtros_ativos', 'media_movel_threshold', 'rodrigo_risco_threshold',
            # Torres Gêmeas params (optional)
            'torres_event_driven', 'torres_event_cooldown_sec',
            'torres_timeframe', 'torres_lookback',
            'torres_tolerancia_pct', 'torres_break_buffer_pct',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def validate_valor_entrada(self, value):
        if value <= 0:
            raise serializers.ValidationError("Valor de entrada deve ser maior que zero.")
        return value
    
    def validate_stop_win(self, value):
        if value <= 0:
            raise serializers.ValidationError("Stop Win deve ser maior que zero.")
        return value
    
    def validate_stop_loss(self, value):
        if value <= 0:
            raise serializers.ValidationError("Stop Loss deve ser maior que zero.")
        return value
    
    def validate_martingale_niveis(self, value):
        if value < 0 or value > 5:
            raise serializers.ValidationError("Níveis de Martingale devem estar entre 0 e 5.")
        return value
    
    def validate_soros_niveis(self, value):
        if value < 0 or value > 10:
            raise serializers.ValidationError("Níveis de Soros devem estar entre 0 e 10.")
        return value

    def validate_torres_event_cooldown_sec(self, value):
        if value < 0 or value > 600:
            raise serializers.ValidationError("Cooldown deve estar entre 0 e 600 segundos.")
        return value

    def validate_torres_timeframe(self, value):
        if value not in (60, 300):
            # Mantemos simples: 60s (M1) ou 300s (M5)
            raise serializers.ValidationError("Timeframe deve ser 60 (M1) ou 300 (M5).")
        return value

    def validate_torres_lookback(self, value):
        if value < 20 or value > 200:
            raise serializers.ValidationError("Lookback deve estar entre 20 e 200.")
        return value


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    
    class Meta:
        model = Notification
        fields = (
            'id', 'type', 'category', 'title', 'message', 
            'read', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
