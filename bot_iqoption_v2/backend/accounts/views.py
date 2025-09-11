from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, TradingConfiguration
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    IQOptionCredentialsSerializer,
    TradingConfigurationSerializer
)


class RegisterView(generics.CreateAPIView):
    """User registration endpoint"""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    """User login endpoint"""
    
    serializer = UserLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = serializer.validated_data['user']
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'user': UserProfileSerializer(user).data,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """User logout endpoint"""
    
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Logout realizado com sucesso.'})
    except Exception:
        return Response(
            {'error': 'Token inválido.'},
            status=status.HTTP_400_BAD_REQUEST
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """User profile endpoint"""
    
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def set_iq_credentials(request):
    """Set IQ Option credentials"""
    
    serializer = IQOptionCredentialsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    user = request.user
    user.set_iq_credentials(
        serializer.validated_data['iq_email'],
        serializer.validated_data['iq_password']
    )
    
    return Response({'message': 'Credenciais da IQ Option salvas com sucesso.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_iq_credentials(request):
    """Check if user has IQ Option credentials"""
    
    user = request.user
    email, password = user.get_iq_credentials()
    
    return Response({
        'has_credentials': bool(email and password),
        'iq_email': email if email else None
    })


class TradingConfigurationView(generics.RetrieveUpdateAPIView):
    """Trading configuration endpoint"""
    
    serializer_class = TradingConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        config, created = TradingConfiguration.objects.get_or_create(
            user=self.request.user
        )
        return config


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_data(request):
    """Get dashboard data for user"""
    
    user = request.user
    email, password = user.get_iq_credentials()
    
    try:
        config = user.trading_config
    except TradingConfiguration.DoesNotExist:
        config = TradingConfiguration.objects.create(user=user)
    
    return Response({
        'user': UserProfileSerializer(user).data,
        'has_iq_credentials': bool(email and password),
        'trading_config': TradingConfigurationSerializer(config).data,
        'is_bot_running': False,  # This will be updated by trading module
    })
