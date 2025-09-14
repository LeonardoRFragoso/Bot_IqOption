from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample notifications for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to create notifications for (default: first user)',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User with ID {user_id} does not exist')
                )
                return
        else:
            user = User.objects.first()
            if not user:
                self.stdout.write(
                    self.style.ERROR('No users found in database')
                )
                return

        # Sample notifications
        notifications_data = [
            {
                'type': 'success',
                'category': 'trading',
                'title': 'Operação Bem-sucedida',
                'message': 'Sua operação em EURUSD foi finalizada com lucro de R$ 15,50',
                'read': False,
            },
            {
                'type': 'warning',
                'category': 'trading',
                'title': 'Stop Loss Ativado',
                'message': 'O stop loss foi ativado para GBPUSD. Perda de R$ 8,20',
                'read': False,
            },
            {
                'type': 'info',
                'category': 'system',
                'title': 'Análise de Ativos Concluída',
                'message': 'A catalogação automática identificou 12 ativos com alta probabilidade',
                'read': True,
            },
            {
                'type': 'error',
                'category': 'system',
                'title': 'Falha na Conexão',
                'message': 'Erro temporário na conexão com a IQ Option. Reconectando...',
                'read': True,
            },
            {
                'type': 'info',
                'category': 'account',
                'title': 'Configuração Atualizada',
                'message': 'Suas preferências de trading foram salvas com sucesso',
                'read': True,
            },
            {
                'type': 'success',
                'category': 'account',
                'title': 'Pagamento Aprovado',
                'message': 'Sua assinatura foi renovada com sucesso. Válida até 14/10/2025',
                'read': False,
            },
        ]

        created_count = 0
        for notification_data in notifications_data:
            notification, created = Notification.objects.get_or_create(
                user=user,
                title=notification_data['title'],
                defaults=notification_data
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} sample notifications for user {user.email}'
            )
        )
