from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import UserLocationLog, HospitalRealtimeStatus, Hospital, Review, Comment, SymptomSearchLog, BookMark, ChatSession
from .serializers import HospitalResponseSerializer, ReviewSerializer, CommentSerializer, HospitalListSerializer
from .constants import HOSPITAL_FIELD_DESC
from .chatbot import ChatbotService
from django.conf import settings
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import Case, When, F, Value, FloatField, Avg, Count, Exists, OuterRef, BooleanField
import requests
import json
import math
import urllib3

# InsecureRequestWarning 경고 억제 (gms.ssafy.io 인증서 문제 대응)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USE_NMC_API = False 

class BookMarkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, hpid):
        hospital = get_object_or_404(Hospital, hpid=hpid)
        user = request.user

        bookmark, created = BookMark.objects.get_or_create(user=user, hospital=hospital)

        if not created:
            # 이미 존재하면 삭제 (Toggle)
            bookmark.delete()
            return Response({
                "result": True,
                "is_bookmarked": False,
                "message": "찜 목록에서 삭제되었습니다."
            }, status=status.HTTP_200_OK)
        
        return Response({
            "result": True,
            "is_bookmarked": True,
            "message": "찜 목록에 추가되었습니다."
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, hpid):
        hospital = get_object_or_404(Hospital, hpid=hpid)
        user = request.user

        try:
            bookmark = BookMark.objects.get(user=user, hospital=hospital)
            bookmark.delete()
            return Response({
                "result": True,
                "is_bookmarked": False,
                "message": "찜 목록에서 삭제되었습니다."
            }, status=status.HTTP_204_NO_CONTENT)
        except BookMark.DoesNotExist:
            return Response({
                "result": False,
                "is_bookmarked": False,
                "message": "찜 목록에 존재하지 않습니다."
            }, status=status.HTTP_404_NOT_FOUND)

class ChatbotView(APIView):
    permission_classes = [permissions.AllowAny] # 누구나 사용 가능

    def post(self, request):
        user = request.user if request.user.is_authenticated else None
        session_id = request.data.get('session_id')
        message = request.data.get('message', '')

        if not message and not session_id:
             # 초기 진입 시
             message = ""
        
        service = ChatbotService()
        try:
            response_data = service.process_message(session_id, message, user)
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Chatbot Error: {e}")
            return Response({"result": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChatbotFinishView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        user = request.user

        if not session_id:
            return Response({"result": False, "message": "Session ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = ChatSession.objects.get(session_id=session_id, user=user)
            session.state = 'DONE'
            session.save()
            return Response({"result": True, "message": "Session finished successfully."}, status=status.HTTP_200_OK)
        except ChatSession.DoesNotExist:
            return Response({"result": False, "message": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"result": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        # radius = data.get('radius') # 사용자 입력 무시

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
            
            # 요구사항: 반경은 50km로 항상 고정
            final_radius = 50 

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

            # --- 챗봇 세션 연동 로직 추가 ---
            chatbot_response = None
            active_session = ChatSession.objects.filter(user=user).exclude(state='DONE').order_by('-updated_at').first()
            
            if active_session:
                # 세션 데이터 업데이트
                collected = active_session.collected_data
                collected['latitude'] = float(lat)
                collected['longitude'] = float(lon)
                collected['location'] = loc_text or '설정된 위치'
                
                # 상태를 위치 확인 단계로 변경
                active_session.state = 'CHECK_LOCATION'
                active_session.collected_data = collected
                
                # 메시지 생성
                msg = f"정보를 모두 수집했습니다.\n현재 위치가 **'{collected['location']}'** 맞으신가요?"
                active_session.history.append({"role": "assistant", "content": msg})
                active_session.save()
                
                chatbot_response = {
                    "session_id": str(active_session.session_id),
                    "message": msg,
                    "state": active_session.state,
                    "is_finished": False,
                    "find_loc": False
                }

            return Response({
                "result": True,
                "chatbot_response": chatbot_response
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"result": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GeneralSymptomView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    # Connection Pooling (Class Level)
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    def post(self, request):
        user = request.user
        data = request.data
        symptoms = data.get('symptom', [])
        gender = data.get('gender') 
        age = data.get('age')       
        refresh = data.get('refresh', False)
        req_sign_kind = data.get('sign_kind')

        if isinstance(refresh, str):
            refresh = refresh.lower() == "true"

        # sign_kind는 로그용으로만 사용 (유저 식별은 request.user로 충분)
        final_sign_kind = 1
        if user.is_authenticated:
            final_sign_kind = user.sign_kind
        elif req_sign_kind is not None:
            try:
                final_sign_kind = int(req_sign_kind)
            except (ValueError, TypeError):
                pass

        # 1. 일일 요청 가능 횟수 체크 및 차감 (인증된 유저만)
        if user.is_authenticated and not refresh:
            if user.remaining_requests != -1: # -1은 무제한
                if user.remaining_requests <= 0:
                    return Response({
                        "result": False, 
                        "message": "일일 요청 가능 횟수를 모두 소진하였습니다. 내일 다시 이용해 주세요."
                    }, status=status.HTTP_403_FORBIDDEN)
                
                # 횟수 차감 및 저장
                user.remaining_requests -= 1
                user.save()
        
        if not symptoms:
            return Response({"result": False, "message": "Symptoms are required."}, status=status.HTTP_400_BAD_REQUEST)

        req_lat = data.get('latitude')
        req_lon = data.get('longitude')
        
        if req_lat and req_lon:
            user_lat = float(req_lat)
            user_lon = float(req_lon)
        else:
            user_lat = user.latitude
            user_lon = user.longitude

        if user_lat is None or user_lon is None:
             return Response({"result": False, "message": "User location not found."}, status=status.HTTP_400_BAD_REQUEST)

        radius = 50
        
        symptoms_str = ",".join(sorted(symptoms)) if symptoms else ""
        
        recent_log = SymptomSearchLog.objects.filter(
            symptoms=symptoms_str,
            gender=gender,
            age=age,
            created_at__gte=timezone.now() - timedelta(hours=1),
            ai_recommended_fields__isnull=False
        ).order_by('-created_at').first()

        cached_data = recent_log
        
        if not cached_data:
            cached_data = SymptomSearchLog.objects.filter(
                symptoms=symptoms_str,
                gender=gender,
                age=age,
                ai_recommended_fields__isnull=False
            ).order_by('-created_at').first()

        if cached_data:
            recommended_fields = cached_data.ai_recommended_fields
            openai_comment = cached_data.openai_comment
        else:
            ai_response = self.get_recommended_fields(symptoms, gender, age)
            recommended_fields = ai_response.get('fields', {})
            openai_comment = ai_response.get('comment', "분석 결과가 없습니다.")

        # 로그 저장
        try:
            SymptomSearchLog.objects.create(
                user=user if user.is_authenticated else None,
                user_email=user.email if user.is_authenticated else "anonymous",
                latitude=user_lat,
                longitude=user_lon,
                radius=radius,
                sign_kind=final_sign_kind,
                symptoms=symptoms_str,
                gender=gender,
                age=age,
                ai_recommended_fields=recommended_fields,
                openai_comment=openai_comment
            )
        except Exception as e:
            print(f"SymptomSearchLog Save Error: {e}")

        if USE_NMC_API:
            nearby_hospitals = self.get_nearby_hospitals_from_api(user_lat, user_lon)
        else:
            nearby_hospitals = self.get_nearby_hospitals_from_db(user_lat, user_lon)
        
        filtered_hospitals = self.filter_by_radius(nearby_hospitals, radius)
        
        processed_data = []
        max_total_score = 0 

        for item in filtered_hospitals:
            hpid = item['hpid']
            distance = item['distance']
            
            try:
                realtime_data = HospitalRealtimeStatus.objects.get(hospital__hpid=hpid)
            except HospitalRealtimeStatus.DoesNotExist:
                realtime_data = None
            
            if not realtime_data:
                continue

            from .models import HospitalSevereMessage
            severe_msgs = HospitalSevereMessage.objects.filter(hospital__hpid=hpid).order_by('-created_at')
            severe_messages_list = [
                {
                    "message": msg.message,
                    "created_at": msg.created_at.strftime('%Y-%m-%d %H:%M:%S') if msg.created_at else ""
                } for msg in severe_msgs
            ]

            raw_score, matched_reasons = self.calculate_score(realtime_data, recommended_fields)
            if raw_score > max_total_score:
                max_total_score = raw_score
            
            hvec = realtime_data.hvec if realtime_data else 0
            hvs01 = realtime_data.hvs01 if realtime_data else 0 
            
            ai_matches = {}
            for field in recommended_fields.keys():
                val = getattr(realtime_data, field, 0) if realtime_data else 0
                ai_matches[field] = val

            hospital_info = {
                "hpid": hpid,
                "name": item['name'],
                "address": item['address'],
                "phone": item['phone'],
                "er_phone": item['er_phone'],
                "distance": distance,
                "raw_score": raw_score,
                "latitude": item['latitude'],
                "longitude": item['longitude'],
                "hvec": hvec,   
                "hvs01": hvs01, 
                "severe_messages": severe_messages_list,
                "ai_matches": ai_matches,
                "matched_reasons": matched_reasons, 
                "hvctayn": realtime_data.hvctayn if realtime_data else None,
                "description": item.get('description'),
            }
            processed_data.append(hospital_info)
            
        for hospital in processed_data:
            if max_total_score > 0:
                normalized_score = round((hospital['raw_score'] / max_total_score) * 100)
            else:
                normalized_score = 0
            hospital['score'] = normalized_score

        sorted_by_distance_data = sorted(processed_data, key=lambda x: x['distance'])
        serialized_distance = HospitalResponseSerializer(sorted_by_distance_data, many=True).data
        
        sorted_by_score_data = sorted(processed_data, key=lambda x: x['score'], reverse=True)
        serialized_score = HospitalResponseSerializer(sorted_by_score_data, many=True).data
        
        return Response({
            "result": True,
            "sorted_by_distance": serialized_distance,
            "sorted_by_score": serialized_score,
            "openai_recommendation": recommended_fields,
            "openai_comment": openai_comment
        }, status=status.HTTP_200_OK)

    def get_recommended_fields(self, symptoms, gender=None, age=None):
        url = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
        api_key = settings.OPENAI_KEY
        
        if not api_key:
            return {'fields': {}, 'comment': "API Key Error"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # [DEBUG] API 키 확인용 (앞 15자리만 출력)
        print(f"[DEBUG] Using API Key: {api_key[:15]}... (Length: {len(api_key)})")
        
        field_desc_str = json.dumps(HOSPITAL_FIELD_DESC, ensure_ascii=False)
        
        user_info = f"User info: Symptoms='{symptoms}'"
        if gender: user_info += f", Gender='{gender}'"
        if age: user_info += f", Age='{age}'"

        prompt = f"""
        {user_info}
        
        Available Hospital Resource Fields (JSON):
        {field_desc_str}
        
        Task: 
        1. Select TOP 10 fields relevant to the condition.
        2. Assign scores (30 down to 12).
        3. Provide a short reasoning comment (Korean) explaining why these fields are prioritized based on age, gender, and symptoms.
        
        Output Format (JSON only):
        {{
            "fields": {{"hvec": 30, "hvctayn": 28, ...}},
            "comment": "환자는 30대 남성으로 심한 두통을 호소하므로 뇌출혈 등을 확인하기 위해 CT, MRI 가용 여부를 최우선으로 고려했습니다."
        }}
        """
        
        data = {
            "model": "gpt-4o",
            "messages": [
                {"role": "developer", "content": "You are a medical assistant. Return only JSON."},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            # Session 사용 및 타임아웃 10초 적용
            response = self.session.post(url, headers=headers, json=data, timeout=10, verify=False)
            res_json = response.json()
            
            if 'choices' not in res_json:
                print(f"OpenAI API Response Error: {res_json}")
                return {'fields': {}, 'comment': "AI 응답 오류"}

            content = res_json['choices'][0]['message']['content']
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            return json.loads(content)
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return {'fields': {}, 'comment': "AI 분석 중 오류가 발생했습니다."}

    def get_nearby_hospitals_from_api(self, lat, lon):
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytLcinfoInqire"
        key = settings.NMC_API_KEY
        params = {'serviceKey': key, 'WGS84_LON': lon, 'WGS84_LAT': lat, 'numOfRows': 100, '_type': 'json'}
        try:
            response = requests.get(url, params=params, timeout=5)
            items = response.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            results = []
            for item in items:
                results.append({
                    'hpid': item.get('hpid'), 'name': item.get('dutyName'), 'address': item.get('dutyAddr'),
                    'phone': item.get('dutyTel1'), 'er_phone': item.get('dutyTel3'),
                    'latitude': float(item.get('wgs84Lat') or 0), 'longitude': float(item.get('wgs84Lon') or 0),
                    'distance': float(item.get('distance', 9999))
                })
            return results
        except: return []

    def get_nearby_hospitals_from_db(self, lat, lon):
        from django.contrib.gis.measure import D
        user_location = Point(lon, lat, srid=4326)
        hospitals = Hospital.objects.filter(location__dwithin=(user_location, D(km=50)), realtime_status__isnull=False).annotate(distance_obj=Distance('location', user_location)).order_by('distance_obj')
        return [{'hpid': h.hpid, 'name': h.name, 'address': h.address, 'phone': h.main_phone, 'er_phone': h.emergency_phone, 'latitude': h.latitude, 'longitude': h.longitude, 'distance': round(h.distance_obj.km, 2), 'description': h.description} for h in hospitals]

    def filter_by_radius(self, hospitals, radius):
        in_radius = [h for h in hospitals if h['distance'] <= radius]
        return in_radius if len(in_radius) >= 5 else hospitals[:5]

    def calculate_score(self, realtime_data, recommended_fields):
        score = 0
        matched_reasons = []
        if not realtime_data: return 0, ["실시간 데이터 없음"]
        hvec = realtime_data.hvec if realtime_data.hvec > 0 else 0
        if hvec > 0:
            bed_score = 40 + (hvec * 5)
            score += bed_score
            matched_reasons.append(f"응급실 일반 병상 {hvec}개 (+{bed_score}점)")
        else: matched_reasons.append("응급실 일반 병상 없음 (0점)")

        for field, weight in recommended_fields.items():
            if not hasattr(realtime_data, field): continue
            val = getattr(realtime_data, field)
            is_available = False
            if isinstance(val, bool): is_available = val
            elif isinstance(val, int): is_available = val > 0
            elif isinstance(val, str): is_available = val.upper() == 'Y'
            if is_available:
                score += weight
                matched_reasons.append(f"추천 장비/시설: {HOSPITAL_FIELD_DESC.get(field, field)} 보유 (+{weight}점)")
        return score, matched_reasons

class HospitalListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        hospitals = Hospital.objects.all().annotate(
            average_rating=Avg('reviews__rating'),
            review_count=Count('reviews')
        ).order_by('first_address', 'name').prefetch_related('realtime_status', 'bookmarked_by')

        if request.user.is_authenticated:
            is_bookmarked_subquery = BookMark.objects.filter(
                hospital=OuterRef('pk'),
                user=request.user
            )
            hospitals = hospitals.annotate(is_bookmarked=Exists(is_bookmarked_subquery))
        else:
             hospitals = hospitals.annotate(is_bookmarked=Value(False, output_field=BooleanField()))
        
        grouped_data = {}
        serializer = HospitalListSerializer(hospitals, many=True, context={'request': request})
        for item in serializer.data:
            category = item.get('first_address') or "기타"
            if category not in grouped_data: grouped_data[category] = []
            grouped_data[category].append(item)
        return Response({"result": True, "count": hospitals.count(), "data": grouped_data}, status=status.HTTP_200_OK)

class ReviewView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, hpid):
        reviews = Review.objects.filter(hospital__hpid=hpid).annotate(comment_count=Count('comments')).order_by('-created_at')
        return Response(ReviewSerializer(reviews, many=True, context={'request': request}).data, status=status.HTTP_200_OK)

    def post(self, request, hpid):
        hospital = get_object_or_404(Hospital, hpid=hpid)
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user, hospital=hospital)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReviewDetailView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_object(self, review_id):
        return get_object_or_404(Review.objects.annotate(comment_count=Count('comments')), id=review_id)

    def get(self, request, review_id):
        return Response(ReviewSerializer(self.get_object(review_id), context={'request': request}).data, status=status.HTTP_200_OK)

    def put(self, request, review_id):
        review = self.get_object(review_id)
        if review.user != request.user: return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        if timezone.now() - review.created_at > timedelta(days=3): return Response({"message": "작성 후 3일이 지나 수정할 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ReviewSerializer(review, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, review_id):
        review = self.get_object(review_id)
        if review.user != request.user: return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        review.delete()
        return Response({"message": "삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)

class CommentView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, review_id):
        comments = Comment.objects.filter(review_id=review_id).order_by('created_at')
        return Response(CommentSerializer(comments, many=True, context={'request': request}).data, status=status.HTTP_200_OK)

    def post(self, request, review_id):
        review = get_object_or_404(Review, id=review_id)
        serializer = CommentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user, review=review)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CommentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, comment_id):
        return get_object_or_404(Comment, id=comment_id)

    def put(self, request, comment_id):
        comment = self.get_object(comment_id)
        if comment.user != request.user: return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        if timezone.now() - comment.created_at > timedelta(days=3): return Response({"message": "작성 후 3일이 지나 수정할 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CommentSerializer(comment, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, comment_id):
        comment = self.get_object(comment_id)
        if comment.user != request.user: return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response({"message": "삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)
