import json
import os
import requests
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from hospitals.models import Hospital

# 수집할 상세 API 목록
ENDPOINTS = [
    "getSpclDiagInfo2.7", "getTrnsprtInfo2.7", "getDtlInfo2.7", "getEqpInfo2.7",
    "getSpcSbjtSdrInfo2.7", "getDgsbjtInfo2.7", "getMedOftInfo2.7", 
    "getFoepAddcInfo2.7", "getNursigGrdInfo2.7", "getSpclHospAsgFldList2.7", "getEtcHstInfo2.7"
]

# 리스트 형태로 반환되는 API들
LIST_TYPE_ENDPOINTS = [
    "getSpclDiagInfo2.7", "getTrnsprtInfo2.7", "getSpcSbjtSdrInfo2.7", 
    "getDgsbjtInfo2.7", "getMedOftInfo2.7", "getFoepAddcInfo2.7", 
    "getNursigGrdInfo2.7", "getSpclHospAsgFldList2.7", "getEtcHstInfo2.7"
]

class Command(BaseCommand):
    help = '7일 주기로 병원 상세 정보를 업데이트하고 요약(description)을 생성합니다.'

    def handle(self, *args, **options):
        self.stdout.write(f"[{datetime.now()}] 병원 상세 정보 및 요약 업데이트 시작...")
        
        # HTTPS 경고 끄기
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        
        SERVICE_KEY = os.getenv("NMC_API_KEY")
        DETAIL_BASE_URL = 'https://apis.data.go.kr/B551182/MadmDtlInfoService2.7'
        
        # 1. 대상 병원 리스트 확보 (DB에서 가져옴)
        hospitals = Hospital.objects.all()
        targets = []
        for h in hospitals:
            targets.append({
                'hpid': h.hpid,
                'hospital_name': h.name,
                'addr': h.address,
                'instance': h
            })

        # 2. ykiho 매칭 (hospitals.json 활용)
        # Note: hospitals.json이 프로젝트 루트에 있다고 가정합니다.
        source_file_path = os.path.join(settings.BASE_DIR, 'hospitals.json')
        if not os.path.exists(source_file_path):
            self.stdout.write(self.style.ERROR(f"매칭용 파일이 없습니다: {source_file_path}"))
            return

        with open(source_file_path, 'r', encoding='utf-8') as f:
            sources = json.load(f)
        
        targets = self.step1_match_ykiho(targets, sources)

        # 3. 상세 정보 수집 (병렬 처리)
        enriched_data = self.step2_fetch_details(targets, SERVICE_KEY, DETAIL_BASE_URL)

        # 4. 요약문 생성 및 DB 반영
        self.stdout.write(f"[{datetime.now()}] 요약문 생성 및 DB 업데이트 중...")
        updated_count = 0
        for data in enriched_data:
            summary_text = self.step3_generate_rule_based_summary(data)
            h_instance = data.get('instance')
            if h_instance:
                h_instance.description = summary_text
                h_instance.save()
                updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(f"[{datetime.now()}] 업데이트 완료! 총 {updated_count}개 병원 정보 갱신됨."))

    def extract_core_name(self, name):
        name = re.sub(r'\([^)]*\)', '', name)
        remove_list = ['의료법인', '재단법인', '사단법인', '학교법인', '주식회사', '종합병원', '병원', '의원', '기독', '대학교']
        for r in remove_list:
            name = name.replace(r, '')
        return name.replace(" ", "").strip()

    def similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()

    # 좌표 거리 계산 (Haversine formula)
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        from math import radians, cos, sin, asin, sqrt, atan2
        
        # 좌표가 없거나 0인 경우 매칭 불가
        if not lat1 or not lon1 or not lat2 or not lon2:
            return 999999

        R = 6371000 # 지구 반지름 (미터)
        dLat = radians(lat2 - lat1)
        dLon = radians(lon2 - lon1)
        
        a = sin(dLat / 2) * sin(dLat / 2) + \
            cos(radians(lat1)) * cos(radians(lat2)) * \
            sin(dLon / 2) * sin(dLon / 2)
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c # 거리 (미터)

    def step1_match_ykiho(self, targets, sources):
        """
        [수정됨] 좌표 기반 매칭 로직
        이름 유사도 대신 위도(latitude), 경도(longitude)를 비교하여 ykiho를 매칭합니다.
        """
        self.stdout.write(f"[{datetime.now()}] 1. 병원 매칭 시작 (좌표 기반)...")
        
        # 소스 데이터 전처리 (좌표 있는 것만)
        source_data = []
        for s in sources:
            # hospitals.json의 필드명 확인 필요 (보통 XPos, YPos 또는 lat, lon)
            # 여기서는 JSON 구조를 추정하여 XPos(경도), YPos(위도)로 가정하거나 
            # 일반적인 공공데이터 필드명인 'YPos'(위도), 'XPos'(경도)를 사용합니다.
            # 만약 hospitals.json에 좌표 필드가 'yadmNm' 처럼 명확하지 않다면 확인 필요.
            # (fetch_hospitals.py에서는 wgs84Lat, wgs84Lon을 썼음)
            
            # JSON 파일의 필드명을 모르므로, fetch_hospitals와 동일한 소스라고 가정하고 
            # wgs84Lat, wgs84Lon 또는 YPos, XPos를 찾습니다.
            try:
                # hospitals.json이 어떤 API 결과인지에 따라 다름.
                # 일단 float 변환 가능한지 체크
                lat = float(s.get('YPos') or s.get('wgs84Lat') or 0)
                lon = float(s.get('XPos') or s.get('wgs84Lon') or 0)
                
                if lat > 0 and lon > 0:
                    source_data.append({
                        'ykiho': s.get('ykiho'),
                        'lat': lat,
                        'lon': lon,
                        'name': s.get('yadmNm')
                    })
            except:
                continue
        
        matched_count = 0
        
        for target in targets:
            # DB 병원 객체 (target['instance'])에서 좌표 가져오기
            h_obj = target['instance']
            if not h_obj.latitude or not h_obj.longitude:
                continue
                
            t_lat = h_obj.latitude
            t_lon = h_obj.longitude
            
            best_match = None
            min_dist = 100 # 100미터 이내만 매칭 허용
            
            for s in source_data:
                # 단순 거리 계산 (유클리드 거리로 1차 필터링하여 속도 최적화 가능하지만 여기선 전체 순회)
                # 위도/경도 차이가 너무 크면 스킵 (약 0.01도 차이 이상)
                if abs(t_lat - s['lat']) > 0.005 or abs(t_lon - s['lon']) > 0.005:
                    continue

                dist = self.calculate_distance(t_lat, t_lon, s['lat'], s['lon'])
                
                if dist < min_dist:
                    min_dist = dist
                    best_match = s
            
            if best_match:
                target['ykiho'] = best_match['ykiho']
                matched_count += 1
        
        self.stdout.write(f"좌표 매칭 완료: {matched_count}/{len(targets)} 성공")
        return targets

    # def step1_match_ykiho_OLD_NAME_BASED(self, targets, sources):
    #     source_data = []
    #     for s in sources:
    #         nm = s.get('yadmNm', '')
    #         if nm:
    #             source_data.append({
    #                 'name': nm,
    #                 'core': self.extract_core_name(nm),
    #                 'ykiho': s.get('ykiho')
    #             })
        
    #     matched_count = 0
    #     for target in targets:
    #         t_name = target['hospital_name']
    #         t_core = self.extract_core_name(t_name)
            
    #         best_match = None
    #         best_score = 0
            
    #         for s in source_data:
    #             score = 0
    #             if len(t_core) >= 2 and len(s['core']) >= 2:
    #                 if t_core == s['core']: score = 0.95
    #                 elif t_core in s['core'] or s['core'] in t_core: score = 0.85
    #                 else: score = self.similar(t_core, s['core'])
    #             else:
    #                 score = self.similar(t_name, s['name'])
                
    #             if score > best_score:
    #                 best_score = score
    #                 best_match = s
            
    #         if best_score >= 0.45:
    #             target['ykiho'] = best_match['ykiho']
    #             matched_count += 1
        
    #     self.stdout.write(f"매칭 완료: {matched_count}/{len(targets)} 성공")
    #     return targets

    def fetch_single_hospital(self, hospital, service_key, base_url):
        ykiho = hospital.get('ykiho')
        if not ykiho: return hospital
        
        for ep in ENDPOINTS:
            url = f"{base_url}/{ep}"
            try:
                resp = requests.get(url, params={'serviceKey': service_key, 'ykiho': ykiho}, verify=False, timeout=5)
                if resp.status_code == 200:
                    details = self.parse_xml_to_dict(resp.content)
                    if details:
                        if ep in LIST_TYPE_ENDPOINTS:
                            hospital[ep] = details
                        else:
                            hospital.update(details[0])
            except Exception:
                pass
        return hospital

    def parse_xml_to_dict(self, xml_bytes):
        try:
            xml_text = xml_bytes.decode('utf-8')
            root = ET.fromstring(xml_text)
            items = []
            for item in root.findall('.//item'):
                item_dict = {child.tag: child.text for child in item}
                items.append(item_dict)
            return items
        except:
            return []

    def step2_fetch_details(self, targets, service_key, base_url):
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.fetch_single_hospital, t, service_key, base_url): t for t in targets}
            count = 0
            for future in as_completed(futures):
                results.append(future.result())
                count += 1
                if count % 50 == 0:
                    self.stdout.write(f"   ... {count}개 병원 데이터 수집 완료")
        return results

    def step3_generate_rule_based_summary(self, hospital):
        name = hospital.get('hospital_name', hospital.get('yadmNm', '이 병원'))
        addr = hospital.get('addr', '주소 정보 없음')
        est_date = hospital.get('estbDd')
        cl_name = hospital.get('clCdNm', '병원')
        
        # 1. 기본 소개
        intro = f"{name}은(는) {addr}에 위치한 {cl_name}입니다."
        if est_date and len(str(est_date)) == 8:
            intro += f" {est_date[:4]}년 {est_date[4:6]}월에 설립되어 지역 의료를 담당하고 있습니다."
        
        # 2. 진료 과목 (최대 10개)
        subjects = []
        if 'getDgsbjtInfo2.7' in hospital:
            for item in hospital['getDgsbjtInfo2.7']:
                if 'dgsbjtCdNm' in item:
                    subjects.append(item['dgsbjtCdNm'])
        
        subj_str = ""
        if subjects:
            top_subjs = ", ".join(subjects[:10])
            subj_str = f"\n주요 진료 과목으로는 {top_subjs} 등이 있어 폭넓은 진료가 가능합니다."
            
        # 3. 의료 장비
        equips = []
        if 'getEqpInfo2.7' in hospital:
            for item in hospital['getEqpInfo2.7']:
                if 'eqpNm' in item:
                    equips.append(item['eqpNm'])
        
        equip_str = ""
        if equips:
            top_equips = ", ".join(equips[:8])
            equip_str = f"\n또한 {top_equips} 등의 최신 의료 장비를 갖추고 있어 정밀한 검사와 진단이 가능합니다."

        # 4. 특수 응급 진료 (있다면)
        special_str = ""
        if 'getSpclDiagInfo2.7' in hospital:
            specials = []
            for item in hospital['getSpclDiagInfo2.7']:
                if 'srchCdNm' in item: # 예: 소아응급, 화상, 심혈관 등
                    specials.append(item['srchCdNm'])
            if specials:
                special_str = f"\n특히 {', '.join(specials)} 분야의 특수 응급 진료가 가능한 기관입니다."

        summary = f"{intro}{subj_str}{equip_str}{special_str}"
        return summary
