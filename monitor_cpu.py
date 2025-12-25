import os
import django
import time
import subprocess
import sys

# Django 환경 설정
sys.path.append('/home/ubuntu/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Finalproject.settings')
django.setup()

from hospitals.models import ChatSession
from django.utils import timezone
from datetime import timedelta

# --- [설정] ---
THRESHOLD_SESSIONS = 4  # 동시 접속자가 4명 이상이면 GPU 가동
CHECK_INTERVAL = 10     # 10초마다 체크

def check_load_and_scale():
    print(f"[{timezone.now()}] 서버 부하 모니터링 중...")
    
    # 최근 5분 이내에 활동이 있었고, 아직 종료되지 않은 세션 수 카운트
    active_cutoff = timezone.now() - timedelta(minutes=5)
    active_sessions = ChatSession.objects.filter(
        updated_at__gte=active_cutoff
    ).exclude(state='DONE').count()
    
    print(f"📊 현재 활성 사용자: {active_sessions}명")
    
    if active_sessions >= THRESHOLD_SESSIONS:
        # 이미 GPU 서버가 설정되어 있는지 .env 확인 (중복 실행 방지)
        # 실제로는 GPU 인스턴스가 이미 켜져 있는지 AWS API로 확인하는 것이 더 정확함
        print("🚨 임계점 초과! GPU 스팟 인스턴스 가동을 시작합니다.")
        try:
            # scale_gpu.py 실행
            subprocess.run(["python3", "/home/ubuntu/app/scale_gpu.py"], check=True)
            print("✅ GPU 확장 스크립트 실행 완료. 모니터링을 종료합니다.")
            sys.exit(0) # 한 번 켰으면 이 스크립트는 임무 완수
        except Exception as e:
            print(f"❌ 확장 실패: {e}")

if __name__ == "__main__":
    print("🛰️ AI 부하 감시병 가동 시작...")
    while True:
        try:
            check_load_and_scale()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)