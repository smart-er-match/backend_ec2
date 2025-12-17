from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
import time

class Command(BaseCommand):
    help = '병원 데이터 초기 구축을 위한 통합 스크립트 (목록 갱신 -> 실시간 데이터 -> 상세 정보/요약)'

    def handle(self, *args, **options):
        total_start = time.time()
        self.stdout.write(self.style.SUCCESS("=== [Step 1] 병원 목록 갱신 (fetch_hospitals) 시작 ==="))
        try:
            call_command('fetch_hospitals')
            self.stdout.write(self.style.SUCCESS(">>> [Step 1] 완료"))
        except Exception as e:
            raise CommandError(f"[Step 1] 실패: {e}")

        self.stdout.write(self.style.SUCCESS("\n=== [Step 2] 실시간 데이터 초기화 (fetch_all_data) 시작 ==="))
        try:
            # 실시간 데이터 테이블이 비어있으면 채우고, 있으면 갱신
            call_command('fetch_all_data')
            self.stdout.write(self.style.SUCCESS(">>> [Step 2] 완료"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"[Step 2] 경고 (진행 계속): {e}"))

        self.stdout.write(self.style.SUCCESS("\n=== [Step 3] 상세 정보 및 요약 업데이트 (update_hospital_desc) 시작 ==="))
        try:
            call_command('update_hospital_desc')
            self.stdout.write(self.style.SUCCESS(">>> [Step 3] 완료"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"[Step 3] 경고: {e}"))

        total_time = time.time() - total_start
        self.stdout.write(self.style.SUCCESS(f"\n🎉 모든 작업이 완료되었습니다! (소요 시간: {total_time:.1f}초)"))
