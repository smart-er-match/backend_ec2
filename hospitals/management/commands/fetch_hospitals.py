import requests
import os
import re
import time
from django.db import transaction
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from hospitals.models import Hospital, Category, UpdateLog

class Command(BaseCommand):
    help = '기존 데이터를 모두 지우고, 최신 응급의료기관 목록으로 갱신합니다. (시/도 명칭 표준화 포함)'

    def handle(self, *args, **options):
        # 1. API 설정
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire"
        KEY = os.getenv("NMC_API_KEY")
        
        if not KEY:
            self.stdout.write(self.style.ERROR("NMC_API_KEY 환경변수가 설정되지 않았습니다."))
            return

        # 시/도 명칭 표준화 매핑
        CITY_MAPPING = {
            "서울": "서울특별시",
            "부산": "부산광역시",
            "대구": "대구광역시",
            "인천": "인천광역시",
            "광주": "광주광역시",
            "대전": "대전광역시",
            "울산": "울산광역시",
            "세종": "세종특별자치시",
            "세종특별자치시": "세종특별자치시", # 이미 풀네임인 경우도 매핑
            "경기": "경기도",
            "강원": "강원특별자치도",
            "강원특별자치도": "강원특별자치도",
            "충북": "충청북도",
            "충남": "충청남도",
            "전북": "전라북도",
            "전북특별자치도": "전라북도",
            "전남": "전라남도",
            "경북": "경상북도",
            "경남": "경상남도",
            "제주": "제주특별자치도",
            "제주특별자치도": "제주특별자치도"
        }

        # numOfRows를 넉넉하게 설정 (전체 리스트)
        params = {
            'serviceKey': KEY,
            'numOfRows': 5000,
            'pageNo': 1,
            '_type': 'json'
        }

        self.stdout.write("최신 병원 목록 데이터 요청 중...")
        
        response = None
        MAX_RETRIES = 3
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    break
                else:
                    self.stdout.write(self.style.WARNING(f"API 요청 실패 (Status: {response.status_code}). {attempt + 1}/{MAX_RETRIES} 재시도 중..."))
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.WARNING(f"네트워크 오류: {e}. {attempt + 1}/{MAX_RETRIES} 재시도 중..."))
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
        
        if not response or response.status_code != 200:
            self.stdout.write(self.style.ERROR("최대 재시도 횟수를 초과했거나 응답을 받지 못했습니다."))
            return

        try:
            try:
                data = response.json()
            except ValueError:
                self.stdout.write(self.style.ERROR(f"JSON 파싱 실패. 응답 내용: {response.text[:200]}"))
                return

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
            
            processed_hospitals = []
            category_names = set()

            for item in item_list:
                full_address = item.get('dutyAddr', '')
                if not full_address:
                    continue
                
                clean_address = re.sub(r'\s+', ' ', full_address).strip()
                addr_parts = clean_address.split(' ')
                
                raw_first = addr_parts[0] if len(addr_parts) > 0 else ''
                
                first_address = CITY_MAPPING.get(raw_first, raw_first)
                
                second_address = addr_parts[1] if len(addr_parts) > 1 else ''
                third_address = ' '.join(addr_parts[2:]) if len(addr_parts) > 2 else ''

                if first_address:
                    category_names.add(first_address)

                try:
                    lat = float(item.get('wgs84Lat')) if item.get('wgs84Lat') else None
                    lon = float(item.get('wgs84Lon')) if item.get('wgs84Lon') else None
                except ValueError:
                    lat, lon = None, None
                
                location = Point(lon, lat, srid=4326) if lat and lon else None

                clean_name = self.clean_hospital_name(item.get('dutyName'))

                hospital = Hospital(
                    hpid=item.get('hpid'),
                    name=clean_name,
                    address=full_address,
                    first_address=first_address,
                    second_address=second_address,
                    third_address=third_address,
                    category_name=item.get('dutyEmclsName'),
                    main_phone=item.get('dutyTel1'),
                    emergency_phone=item.get('dutyTel3'),
                    latitude=lat,
                    longitude=lon,
                    location=location,
                )
                processed_hospitals.append(hospital)

            with transaction.atomic():
                Hospital.objects.all().delete()
                Category.objects.all().delete()

                category_objects = [Category(name=name) for name in sorted(category_names)]
                Category.objects.bulk_create(category_objects)

                Hospital.objects.bulk_create(processed_hospitals)
                
                UpdateLog.objects.update_or_create(update_key='base', defaults={})

            self.stdout.write(self.style.SUCCESS(f'갱신 완료! 총 {len(processed_hospitals)}개의 병원 데이터와 {len(category_objects)}개의 카테고리가 저장되었습니다.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'업데이트 실패: {e}'))

    def clean_hospital_name(self, name):
        if not name:
            return ""
        
        # 1. 뒤에 괄호가 붙은 형태 먼저 제거
        priority_remove = ['의료법인)', '학교법인)', '재단법인)', '사단법인)', '사회복지법인)']
        for keyword in priority_remove:
            name = name.replace(keyword, '')

        # 2. 일반 키워드 제거
        remove_keywords = ['의료법인', '학교법인', '재단법인', '사단법인', '사회복지법인']
        for keyword in remove_keywords:
            name = name.replace(keyword, '')
        
        # 3. (의), (주) 등 1~2글자 괄호 패턴 제거
        name = re.sub(r'\([가-힣]{1,2}\)', '', name)
        
        return name.strip()