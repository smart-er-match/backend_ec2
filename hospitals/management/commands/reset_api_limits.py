from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Reset daily API request limits for users'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # 1. 파라메틱 (면허 인증된 유저) -> 무제한 (-1)
        count_paramedic = User.objects.filter(is_license_verified=True).update(remaining_requests=-1)
        
        # 2. 토큰 승인된 유저 (token_status=3) 이면서 파라메틱이 아닌 경우 -> 100회
        count_token = User.objects.filter(token_status=3, is_license_verified=False).update(remaining_requests=100)
        
        # 3. 일반 유저 (면허 인증 X, 토큰 승인 X) -> 10회
        # token_status가 3이 아니거나 NULL인 경우
        count_general = User.objects.filter(is_license_verified=False).exclude(token_status=3).update(remaining_requests=10)

        self.stdout.write(self.style.SUCCESS(
            f'Reset Complete.\n'
            f'- Paramedic (-1): {count_paramedic}\n'
            f'- Token User (100): {count_token}\n'
            f'- General User (10): {count_general}'
        ))