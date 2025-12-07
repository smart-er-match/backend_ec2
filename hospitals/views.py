from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import UserLocationLog, HospitalRealtimeStatus, Hospital, Review, Comment
from .serializers import HospitalResponseSerializer, ReviewSerializer, CommentSerializer
from .constants import HOSPITAL_FIELD_DESC
from django.conf import settings
import requests
import json
import math

USE_NMC_API = False 

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
        symptoms = data.get('symptom', [])
        
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

        radius = user.radius if user.radius else 10
        
        recommended_fields = self.get_recommended_fields(symptoms)
        
        if USE_NMC_API:
            nearby_hospitals = self.get_nearby_hospitals_from_api(user_lat, user_lon)
        else:
            nearby_hospitals = self.get_nearby_hospitals_from_db(user_lat, user_lon)
        
        filtered_hospitals = self.filter_by_radius(nearby_hospitals, radius)
        
        processed_data = []
        for item in filtered_hospitals:
            hpid = item['hpid']
            distance = item['distance']
            
            try:
                realtime_data = HospitalRealtimeStatus.objects.get(hospital__hpid=hpid)
            except HospitalRealtimeStatus.DoesNotExist:
                realtime_data = None
            
            score, matched_reasons = self.calculate_score(realtime_data, recommended_fields)
            
            hospital_info = {
                "hpid": hpid,
                "name": item['name'],
                "address": item['address'],
                "phone": item['phone'],
                "er_phone": item['er_phone'],
                "distance": distance,
                "score": score,
                "matched_reasons": matched_reasons, 
                "latitude": item['latitude'],
                "longitude": item['longitude'],
                "hvec": realtime_data.hvec if realtime_data else None,
                "hvctayn": realtime_data.hvctayn if realtime_data else None,
            }
            processed_data.append(hospital_info)
            
        sorted_by_distance_data = sorted(processed_data, key=lambda x: x['distance'])
        serialized_distance = HospitalResponseSerializer(sorted_by_distance_data, many=True).data
        
        sorted_by_score_data = sorted(processed_data, key=lambda x: x['score'], reverse=True)
        serialized_score = HospitalResponseSerializer(sorted_by_score_data, many=True).data
        
        return Response({
            "result": True,
            "sorted_by_distance": serialized_distance,
            "sorted_by_score": serialized_score,
            "openai_recommendation": recommended_fields 
        }, status=status.HTTP_200_OK)

    def get_recommended_fields(self, symptoms):
        url = "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions"
        api_key = settings.OPENAI_KEY
        
        if not api_key:
            return {}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        field_desc_str = json.dumps(HOSPITAL_FIELD_DESC, ensure_ascii=False)
        prompt = f"""
        User symptoms: {symptoms}
        Available Hospital Resource Fields (JSON):
        {field_desc_str}
        Task: Select TOP 10 fields. Score 30 down to 12.
        Output: JSON only.
        Example: {{"hvec": 30, "hvctayn": 28}}
        """
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a medical assistant. Return only JSON."},
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10, verify=False)
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
                
            return json.loads(content)
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return {}

    def get_nearby_hospitals_from_api(self, lat, lon):
        url = "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytLcinfoInqire"
        key = settings.NMC_API_KEY
        params = {
            'serviceKey': key,
            'WGS84_LON': lon,
            'WGS84_LAT': lat,
            'numOfRows': 100,
            'pageNo': 1,
            '_type': 'json'
        }
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            
            results = []
            for item in items:
                try:
                    dist = float(item.get('distance', 9999))
                except:
                    dist = 9999
                
                if item.get('hpid'):
                    results.append({
                        'hpid': item.get('hpid'),
                        'name': item.get('dutyName'),
                        'address': item.get('dutyAddr'),
                        'phone': item.get('dutyTel1'),
                        'er_phone': item.get('dutyTel3'),
                        'latitude': float(item.get('wgs84Lat') or 0),
                        'longitude': float(item.get('wgs84Lon') or 0),
                        'distance': dist
                    })
            return results
        except Exception as e:
            print(f"NMC API Error: {e}")
            return []

    def get_nearby_hospitals_from_db(self, lat, lon):
        hospitals = Hospital.objects.all()
        results = []
        
        for h in hospitals:
            if h.latitude is None or h.longitude is None:
                continue
                
            dist = self.haversine(lat, lon, h.latitude, h.longitude)
            results.append({
                'hpid': h.hpid,
                'name': h.name,
                'address': h.address,
                'phone': h.main_phone,
                'er_phone': h.emergency_phone,
                'latitude': h.latitude,
                'longitude': h.longitude,
                'distance': dist
            })
        return results

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6371
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dLon / 2) * math.sin(dLon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        d = R * c
        return round(d, 2)

    def filter_by_radius(self, hospitals, radius):
        sorted_hospitals = sorted(hospitals, key=lambda x: x['distance'])
        in_radius = [h for h in sorted_hospitals if h['distance'] <= radius]
        if len(in_radius) < 5:
            return sorted_hospitals[:5]
        return in_radius

    def calculate_score(self, realtime_data, recommended_fields):
        score = 0
        matched_reasons = []
        
        if not realtime_data:
            return 0, []

        if realtime_data.hvec > 0:
            score += realtime_data.hvec * 0.1

        for field, weight in recommended_fields.items():
            if not hasattr(realtime_data, field):
                continue
            val = getattr(realtime_data, field)
            
            is_available = False
            if isinstance(val, bool): is_available = val
            elif isinstance(val, int): is_available = val > 0
            elif isinstance(val, str): is_available = val.upper() == 'Y'
            
            if is_available:
                score += weight
                matched_reasons.append(f"{HOSPITAL_FIELD_DESC.get(field, field)} ({weight}점)")
        
        return score, matched_reasons

class ReviewView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, hpid):
        reviews = Review.objects.filter(hospital__hpid=hpid).order_by('-created_at')
        serializer = ReviewSerializer(reviews, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, hpid):
        hospital = get_object_or_404(Hospital, hpid=hpid)
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user, hospital=hospital)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReviewDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, review_id):
        return get_object_or_404(Review, id=review_id)

    def check_permission(self, review, user):
        if review.user != user:
            return False
        return True

    def check_editable(self, review):
        # 3일 이내인지 확인
        if timezone.now() - review.created_at > timedelta(days=3):
            return False
        return True

    def put(self, request, review_id):
        review = self.get_object(review_id)
        if not self.check_permission(review, request.user):
            return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        
        if not self.check_editable(review):
            return Response({"message": "작성 후 3일이 지나 수정할 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ReviewSerializer(review, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, review_id):
        review = self.get_object(review_id)
        if not self.check_permission(review, request.user):
            return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        
        review.delete()
        return Response({"message": "삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)

class CommentView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

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

    def check_permission(self, comment, user):
        return comment.user == user

    def check_editable(self, comment):
        if timezone.now() - comment.created_at > timedelta(days=3):
            return False
        return True

    def put(self, request, comment_id):
        comment = self.get_object(comment_id)
        if not self.check_permission(comment, request.user):
            return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        
        if not self.check_editable(comment):
            return Response({"message": "작성 후 3일이 지나 수정할 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)

        serializer = CommentSerializer(comment, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, comment_id):
        comment = self.get_object(comment_id)
        if not self.check_permission(comment, request.user):
            return Response({"message": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
        
        comment.delete()
        return Response({"message": "삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT)