import requests
import os
from django.db import transaction
from django.core.management.base import BaseCommand
from hospitals.models import Hospital, Category, UpdateLog

class Command(BaseCommand):
    help = '기존 데이터를 모두 지우고, 최신 응급의료기관 목록으로 갱신합니다.'

    def handle(self, *args, **options):
        # 1. API 설정
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire"
        KEY = os.getenv("NMC_API_KEY")
        
        if not KEY:
            self.stdout.write(self.style.ERROR("NMC_API_KEY 환경변수가 설정되지 않았습니다."))
            return

        # numOfRows를 넉넉하게 설정 (전체 리스트)
        params = {
            'serviceKey': KEY,
            'numOfRows': 5000,  # 전국 응급의료기관 수는 500개 내외이나 넉넉히
            'pageNo': 1,
            '_type': 'json'
        }

        self.stdout.write("최신 병원 목록 데이터 요청 중...")
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            # JSON 파싱 시도 (서비스키 에러 시 XML로 올 수 있음)
            try:
                data = response.json()
            except ValueError:
                self.stdout.write(self.style.ERROR(f"JSON 파싱 실패. 응답 내용: {response.text[:200]}"))
                return

            # 응답 구조 확인
            if 'response' not in data or 'body' not in data['response'] or 'items' not in data['response']['body']:
                self.stdout.write(self.style.ERROR(f"API 응답 구조 오류: {data}"))
                return

            items = data['response']['body']['items']
            if not items:
                self.stdout.write(self.style.WARNING("데이터가 없습니다."))
                return
                
            item_list = items.get('item', [])
            if isinstance(item_list, dict):
                item_list = [item_list]
            
            # 주소 전처리 및 카테고리 수집
            processed_hospitals = []
            category_names = set()

            for item in item_list:
                full_address = item.get('dutyAddr', '')
                if not full_address:
                    continue
                
                addr_parts = full_address.split()
                first_address = addr_parts[0] if len(addr_parts) > 0 else ''
                second_address = addr_parts[1] if len(addr_parts) > 1 else ''
                third_address = ' '.join(addr_parts[2:]) if len(addr_parts) > 2 else ''

                # 카테고리용 (시/도)
                if first_address:
                    category_names.add(first_address)

                try:
                    lat = float(item.get('wgs84Lat')) if item.get('wgs84Lat') else None
                    lon = float(item.get('wgs84Lon')) if item.get('wgs84Lon') else None
                except ValueError:
                    lat, lon = None, None

                hospital = Hospital(
                    hpid=item.get('hpid'),
                    name=item.get('dutyName'),
                    address=full_address,
                    first_address=first_address,
                    second_address=second_address,
                    third_address=third_address,
                    category_name=item.get('dutyEmclsName'),
                    main_phone=item.get('dutyTel1'),
                    emergency_phone=item.get('dutyTel3'),
                    latitude=lat,
                    longitude=lon,
                )
                processed_hospitals.append(hospital)

            # 3. 트랜잭션: 지우고 쓰는 과정을 '하나의 작업'으로 묶음
            with transaction.atomic():
                # (1) 기존 데이터 전체 삭제 (Cascade로 하위 데이터도 삭제됨)
                Hospital.objects.all().delete()
                Category.objects.all().delete()

                # (2) 카테고리 생성
                category_objects = [Category(name=name) for name in sorted(category_names)]
                Category.objects.bulk_create(category_objects)

                # (3) 새 병원 데이터 저장
                Hospital.objects.bulk_create(processed_hospitals)
                
                # (4) 업데이트 로그 기록
                UpdateLog.objects.update_or_create(update_key='base', defaults={})

            self.stdout.write(self.style.SUCCESS(f'갱신 완료! 총 {len(processed_hospitals)}개의 병원 데이터와 {len(category_objects)}개의 카테고리가 저장되었습니다.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'업데이트 실패: {e}'))