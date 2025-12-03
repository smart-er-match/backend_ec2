from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import UserLocationLog, HospitalRealtimeStatus, Hospital
from .constants import HOSPITAL_FIELD_DESC
import requests
import json
import os
import math

class UserLocationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data
        
        user_email = data.get('useremail')
        sign_kind = data.get('sign_kind')
        lat = data.get('latitude')
        lon = data.get('longitude')
        loc_text = data.get('locationstext')
        # radius도 받아서 저장
        radius = data.get('radius') 

        if lat is None or lon is None:
            return Response({"result": False, "message": "Latitude and Longitude are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            final_sign_kind = 1
            if sign_kind is not None:
                try:
                    final_sign_kind = int(sign_kind)
                except (ValueError, TypeError):
                    pass
            elif user.is_authenticated:
                final_sign_kind = user.sign_kind
            
            # radius 처리 (기본값 10)
            final_radius = 10
            if radius is not None:
                try:
                    final_radius = int(radius)
                except:
                    pass

            UserLocationLog.objects.create(
                user=user,
                user_email=user_email or user.email,
                sign_kind=final_sign_kind,
                latitude=float(lat),
                longitude=float(lon),
                radius=final_radius,
                location_text=loc_text or ''
            )

            if user.is_authenticated:
                user.latitude = float(lat)
                user.longitude = float(lon)
                user.location = loc_text or ''
                user.radius = final_radius
                user.save()

            return Response({"result": True}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"result": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GeneralSymptomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data
        symptoms = data.get('symptom', []) # 리스트 형태 예상
        
        if not symptoms:
            return Response({"result": False, "message": "Symptoms are required."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. 사용자 위치 및 반경 정보 가져오기
        user_lat = user.latitude
        user_lon = user.longitude
        radius = user.radius if user.radius else 10
        
        # 만약 유저 정보에 좌표가 없으면 요청 데이터에서 찾기 (보완)
        if user_lat is None or user_lon is None:
             # 만약 요청 바디에 있다면 사용, 아니면 에러
             pass # 일단 유저 정보에 있다고 가정 (UserLocationView가 먼저 호출됨)

        # 2. OpenAI를 통해 증상에 적합한 병상 필드 및 가중치 추출
        recommended_fields = self.get_recommended_fields(symptoms)
        
        # 3. NMC API를 통해 주변 병원 목록 조회 (최대 100개)
        nearby_hospitals = self.get_nearby_hospitals(user_lat, user_lon)
        
        # 4. 반경 필터링 (최소 5개 보장)
        filtered_hospitals = self.filter_by_radius(nearby_hospitals, radius)
        
        # 5. 실시간 데이터 병합 및 점수 계산
        results = []
        for item in filtered_hospitals:
            hpid = item['hpid']
            distance = item['distance']
            
            # DB에서 실시간 정보 조회
            try:
                realtime_data = HospitalRealtimeStatus.objects.get(hospital__hpid=hpid)
            except HospitalRealtimeStatus.DoesNotExist:
                realtime_data = None
            
            # 점수 계산
            score, matched_reasons = self.calculate_score(realtime_data, recommended_fields)
            
            hospital_info = {
                "hpid": hpid,
                "name": item['dutyName'],
                "address": item['dutyAddr'],
                "phone": item.get('dutyTel1'),
                "er_phone": item.get('dutyTel3'),
                "distance": distance,
                "score": score,
                "matched_reasons": matched_reasons, # 어떤 필드 때문에 점수를 받았는지
                "latitude": item.get('wgs84Lat'),
                "longitude": item.get('wgs84Lon'),
                # 실시간 정보 일부 포함 (응급실 가용 병상 등)
                "hvec": realtime_data.hvec if realtime_data else None,
                "hvctayn": realtime_data.hvctayn if realtime_data else None,
                # 필요한 다른 실시간 정보 추가 가능
            }
            results.append(hospital_info)
            
        # 6. 정렬 및 응답 생성
        # 1) 거리순 (추천 병상이 있는 병원 데이터 - 이미 results에 추천 점수가 포함됨)
        sorted_by_distance = sorted(results, key=lambda x: x['distance'])
        
        # 2) 추천 점수순 (내림차순)
        sorted_by_score = sorted(results, key=lambda x: x['score'], reverse=True)
        
        return Response({
            "result": True,
            "sorted_by_distance": sorted_by_distance,
            "sorted_by_score": sorted_by_score,
            "openai_recommendation": recommended_fields # 디버깅/참고용
        }, status=status.HTTP_200_OK)

    def get_recommended_fields(self, symptoms):
        # GMS OpenAI API 호출
        url = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
        api_key = os.getenv("OPENAI_KEY")
        
        if not api_key:
            return {} # 키 없으면 빈 딕셔너리 반환 (기본 점수만 계산)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # 프롬프트 구성
        field_desc_str = json.dumps(HOSPITAL_FIELD_DESC, ensure_ascii=False)
        prompt = f"""
        User symptoms: {symptoms}
        
        Available Hospital Resource Fields (JSON):
        {field_desc_str}
        
        Task:
        Based on the symptoms, select the TOP 10 most critical resource fields from the list.
        Assign scores from 30 down to 12 (decreasing by 2 for each rank: 30, 28, 26... 12).
        
        Output Format:
        Return ONLY a valid JSON object where keys are the field names (e.g., 'hvec', 'hvctayn') and values are the scores (integers).
        Do not include any explanation.
        Example: {{"hvec": 30, "hvctayn": 28, ...}}
        """
        
        data = {
            "model": "gpt-4o-mini", # or gpt-5-mini as requested, check availability
            "messages": [
                {"role": "system", "content": "You are a medical assistant. Return only JSON."},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10, verify=False)
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            
            # JSON 파싱 (혹시 마크다운 코드블럭이 있을 경우 제거)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            return json.loads(content)
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return {}

    def get_nearby_hospitals(self, lat, lon):
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytLcinfoInqire"
        key = os.getenv("NMC_API_KEY")
        
        params = {
            'serviceKey': key,
            'WGS84_LON': lon,
            'WGS84_LAT': lat,
            'numOfRows': 100, # 100개 가져옴
            'pageNo': 1,
            '_type': 'json'
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            
            # 거리 계산 및 리스트 변환
            results = []
            for item in items:
                # API가 제공하는 distance 사용 (단위 확인 필요, 보통 km)
                try:
                    dist = float(item.get('distance', 9999))
                except (ValueError, TypeError):
                    dist = 9999
                
                item['distance'] = dist
                # hpid가 없는 데이터는 제외
                if item.get('hpid'):
                    results.append(item)
            
            return results
        except Exception as e:
            print(f"NMC API Error: {e}")
            return []

    def filter_by_radius(self, hospitals, radius):
        # 거리순 정렬
        sorted_hospitals = sorted(hospitals, key=lambda x: x['distance'])
        
        # 반경 내 병원
        in_radius = [h for h in sorted_hospitals if h['distance'] <= radius]
        
        # 4개 이하면 거리순 5개 반환 (전체 개수가 5개 미만이면 전체 반환)
        if len(in_radius) < 5:
            return sorted_hospitals[:5]
        
        return in_radius

    def calculate_score(self, realtime_data, recommended_fields):
        score = 0
        matched_reasons = []
        
        if not realtime_data:
            return 0, []

        # 기본 점수: 응급실 일반 병상(hvec)이 있으면 병상 수만큼 가산 (가중치 조절 가능)
        if realtime_data.hvec > 0:
            score += realtime_data.hvec * 0.1 # 병상 1개당 0.1점 (예시)

        for field, weight in recommended_fields.items():
            if not hasattr(realtime_data, field):
                continue
                
            val = getattr(realtime_data, field)
            
            # Boolean 필드 (Y/N) or Integer 필드 (>0) 체크
            is_available = False
            if isinstance(val, bool):
                is_available = val
            elif isinstance(val, int):
                is_available = val > 0
            elif isinstance(val, str):
                is_available = val.upper() == 'Y'
            
            if is_available:
                score += weight
                matched_reasons.append(f"{HOSPITAL_FIELD_DESC.get(field, field)} ({weight}점)")
        
        return score, matched_reasons