from django.core.management.base import BaseCommand
from accounts.models import TradingConfiguration


class Command(BaseCommand):
    help = 'Clear stale filter data from TradingConfiguration'

    def handle(self, *args, **options):
        # Clear filtros_ativos for all users
        updated = TradingConfiguration.objects.update(filtros_ativos=[])
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cleared filtros_ativos for {updated} trading configurations'
            )
        )
        
        # Show current state
        configs = TradingConfiguration.objects.all()
        for config in configs:
            self.stdout.write(
                f'User: {config.user.email} - Filtros: {config.filtros_ativos}'
            )
