from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, TradingConfiguration, Notification
from .serializers import (
    UserRegistrationSerializer,
    TradingConfigurationSerializer,
    NotificationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    IQOptionCredentialsSerializer
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


# Notification Views
class NotificationListView(generics.ListAPIView):
    """List user notifications"""
    
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark notification as read"""
    
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.read = True
        notification.save()
        
        return Response({
            'message': 'Notificação marcada como lida',
            'notification': NotificationSerializer(notification).data
        })
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notificação não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    
    updated_count = Notification.objects.filter(
        user=request.user,
        read=False
    ).update(read=True)
    
    return Response({
        'message': f'{updated_count} notificações marcadas como lidas'
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete notification"""
    
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.delete()
        
        return Response({
            'message': 'Notificação excluída com sucesso'
        })
    except Notification.DoesNotExist:
        return Response(
            {'error': 'Notificação não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_all_notifications(request):
    """Clear all notifications"""
    
    deleted_count, _ = Notification.objects.filter(
        user=request.user
    ).delete()
    
    return Response({
        'message': f'{deleted_count} notificações excluídas'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_count(request):
    """Get notification counts"""
    
    total = Notification.objects.filter(user=request.user).count()
    unread = Notification.objects.filter(user=request.user, read=False).count()
    
    return Response({
        'total': total,
        'unread': unread
    })


def create_notification(user, notification_type, category, title, message):
    """Helper function to create notifications"""
    
    return Notification.objects.create(
        user=user,
        type=notification_type,
        category=category,
        title=title,
        message=message
    )
