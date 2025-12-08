from django.db import models
from django.contrib.gis.db import models as gis_models
from accounts.models import User
import json
import uuid

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Hospital(models.Model):
    hpid = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    first_address = models.CharField(max_length=50, blank=True)
    second_address = models.CharField(max_length=50, blank=True)
    third_address = models.CharField(max_length=100, blank=True)
    category_name = models.CharField(max_length=50, blank=True, null=True)
    main_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_phone = models.CharField(max_length=20, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location = gis_models.PointField(null=True, blank=True, srid=4326, geography=True)
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.hpid}] {self.name}"

class Review(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hospital_reviews')
    content = models.TextField()
    rating = models.IntegerField(default=5) # 1~5점
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.hospital.name} - {self.user.name}"

class Comment(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment by {self.user.name}"

class HospitalRealtimeStatus(models.Model):
    hospital = models.OneToOneField(Hospital, on_delete=models.CASCADE, related_name='realtime_status')
    
    # 응답 XML 필드 그대로 매핑 (hv*)
    hv10 = models.CharField(max_length=10, blank=True, null=True)
    hv11 = models.CharField(max_length=10, blank=True, null=True)
    hv13 = models.IntegerField(default=0)
    hv14 = models.IntegerField(default=0)
    hv18 = models.IntegerField(default=0)
    hv2 = models.IntegerField(default=0)
    hv24 = models.IntegerField(default=0)
    hv25 = models.IntegerField(default=0)
    hv27 = models.IntegerField(default=0)
    hv28 = models.IntegerField(default=0)
    hv29 = models.IntegerField(default=0)
    hv3 = models.IntegerField(default=0)
    hv30 = models.IntegerField(default=0)
    hv31 = models.IntegerField(default=0)
    hv34 = models.IntegerField(default=0)
    hv35 = models.IntegerField(default=0)
    hv36 = models.IntegerField(default=0)
    hv38 = models.IntegerField(default=0)
    hv40 = models.IntegerField(default=0)
    hv41 = models.IntegerField(default=0)
    hv42 = models.CharField(max_length=10, blank=True, null=True)
    hv5 = models.CharField(max_length=10, blank=True, null=True)
    hv7 = models.CharField(max_length=10, blank=True, null=True)
    hvamyn = models.CharField(max_length=10, blank=True, null=True)
    hvangioayn = models.CharField(max_length=10, blank=True, null=True)
    hvcrrtayn = models.CharField(max_length=10, blank=True, null=True)
    hvctayn = models.CharField(max_length=10, blank=True, null=True)
    hvec = models.IntegerField(default=0)
    hvecmoayn = models.CharField(max_length=10, blank=True, null=True)
    hvgc = models.IntegerField(default=0)
    hvcc = models.IntegerField(default=0) # 신경과 중환자실
    hvccc = models.IntegerField(default=0) # 흉부외과 중환자실
    hvicc = models.IntegerField(default=0) # 일반 중환자실
    hvhypoayn = models.CharField(max_length=10, blank=True, null=True)
    hvidate = models.CharField(max_length=20, blank=True, null=True)
    hvincuayn = models.CharField(max_length=10, blank=True, null=True)
    hvmriayn = models.CharField(max_length=10, blank=True, null=True)
    hvncc = models.IntegerField(default=0)
    hvoc = models.IntegerField(default=0)
    hvoxyayn = models.CharField(max_length=10, blank=True, null=True)
    hvs01 = models.IntegerField(default=0)
    hvs02 = models.IntegerField(default=0)
    hvs03 = models.IntegerField(default=0)
    hvs04 = models.IntegerField(default=0)
    hvs05 = models.IntegerField(default=0)
    hvs06 = models.IntegerField(default=0)
    hvs07 = models.IntegerField(default=0)
    hvs08 = models.IntegerField(default=0)
    hvs15 = models.IntegerField(default=0)
    hvs18 = models.IntegerField(default=0)
    hvs19 = models.IntegerField(default=0)
    hvs21 = models.IntegerField(default=0)
    hvs22 = models.IntegerField(default=0)
    hvs24 = models.IntegerField(default=0)
    hvs25 = models.IntegerField(default=0)
    hvs26 = models.IntegerField(default=0)
    hvs27 = models.IntegerField(default=0)
    hvs28 = models.IntegerField(default=0)
    hvs29 = models.IntegerField(default=0)
    hvs30 = models.IntegerField(default=0)
    hvs31 = models.IntegerField(default=0)
    hvs32 = models.IntegerField(default=0)
    hvs33 = models.IntegerField(default=0)
    hvs34 = models.IntegerField(default=0)
    hvs35 = models.IntegerField(default=0)
    hvs38 = models.IntegerField(default=0)
    hvs46 = models.IntegerField(default=0)
    hvs47 = models.IntegerField(default=0)
    hvs51 = models.IntegerField(default=0)
    hvs56 = models.IntegerField(default=0)
    hvs57 = models.IntegerField(default=0)
    hvs59 = models.IntegerField(default=0)
    hvventiayn = models.CharField(max_length=10, blank=True, null=True)
    hvventisoayn = models.CharField(max_length=10, blank=True, null=True)
    
    last_updated = models.DateTimeField(auto_now=True)

class HospitalSevereMessage(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='severe_messages')
    message = models.TextField(blank=True, null=True) # symBlkMsg
    message_type = models.CharField(max_length=20, blank=True, null=True) # symBlkMsgTyp (응급/중증)
    severe_code = models.CharField(max_length=10, blank=True, null=True) # symTypCod (Y000 등)
    severe_name = models.CharField(max_length=50, blank=True, null=True) # symTypCodMag
    display_yn = models.CharField(max_length=5, blank=True, null=True) # symOutDspYon (Y/N)
    display_method = models.CharField(max_length=10, blank=True, null=True) # symOutDspMth
    start_time = models.CharField(max_length=20, blank=True, null=True) # symBlkSttDtm
    end_time = models.CharField(max_length=20, blank=True, null=True) # symBlkEndDtm
    
    created_at = models.DateTimeField(auto_now_add=True)

class SymptomSearchLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    user_email = models.EmailField(blank=True, null=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius = models.IntegerField(default=10)
    sign_kind = models.IntegerField(default=1) # 소셜 종류 추가 (1: Email, 2: Kakao, 3: Naver, 4: Google)
    symptoms = models.TextField(blank=True, null=True) # 증상 목록 (쉼표 등으로 구분된 문자열)
    gender = models.CharField(max_length=10, blank=True, null=True)
    age = models.CharField(max_length=20, blank=True, null=True) # Integer에서 Char로 변경
    ai_recommended_fields = models.JSONField(blank=True, null=True) # AI 추천 필드 저장
    openai_comment = models.TextField(blank=True, null=True)        # AI 코멘트 저장
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_email} - {self.symptoms} @ ({self.latitude},{self.longitude})"

class UpdateLog(models.Model):
    update_key = models.CharField(max_length=20, primary_key=True)
    updated_at = models.DateTimeField(auto_now=True)

class UserLocationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    user_email = models.EmailField(blank=True, null=True)
    sign_kind = models.IntegerField(default=1)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius = models.IntegerField(default=10) # 반경 (km)
    location_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_email} - {self.location_text} ({self.created_at})"

class BookMark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'hospital'], name='unique_user_hospital_bookmark')
        ]

    def __str__(self):
        return f"{self.user.name} - {self.hospital.name}"

class ChatSession(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    # 대화 상태: INIT -> ASK_INFO(나이/성별) -> ASK_SYMPTOM -> ASK_HISTORY -> CONFIRM -> DONE
    state = models.CharField(max_length=50, default='INIT')
    
    # 수집된 데이터 (JSON)
    # 예: {"age": "30대", "gender": "M", "symptoms": ["두통"], "history": "고혈압"}
    collected_data = models.JSONField(default=dict)
    
    # 대화 로그 (선택 사항, 디버깅용)
    history = models.JSONField(default=list)
    
    # 사용된 AI 모델 (CPU/GPU)
    ai_model_used = models.CharField(max_length=50, default='NONE', blank=True, null=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.session_id} ({self.state})"