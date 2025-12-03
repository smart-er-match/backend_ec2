from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


class User(AbstractUser):
    class SignKind(models.IntegerChoices):
        EMAIL = 1, "Email"
        KAKAO = 2, "Kakao"
        NAVER = 3, "Naver"

    class Gender(models.TextChoices):
        MALE = 'M', '남성'
        FEMALE = 'F', '여성'

    # username은 로그인 식별자이자 채널별 고유값(일반: 이메일, 카카오: kakao_id, 네이버: naver_id)
    username = models.CharField(max_length=150, unique=True)
    role = models.BooleanField(null=True, blank=True, default=False)
    email = models.EmailField(max_length=254)
    sign_kind = models.PositiveSmallIntegerField(choices=SignKind.choices, default=SignKind.EMAIL)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        null=True,
        blank=True,
        default=None,
    )
    kakao_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    naver_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    # 면허 관련 필드
    license_kind = models.CharField(max_length=50, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    license_date = models.CharField(max_length=20, blank=True, null=True)  # 면허발급일 (YYYYMMDD)
    is_license_verified = models.BooleanField(default=False)  # 면허 인증 여부

    # 위치 정보 필드 추가
    location = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    radius = models.IntegerField(default=10)  # 반경 (km)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "sign_kind"],
                name="user_email_sign_kind_unique",
            ),
        ]

class ParamedicAuthHistory(models.Model):
    """
    파라메트릭 인증 요청 이력 저장
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_histories')
    
    # 요청 데이터
    login_option = models.CharField(max_length=10)
    jumin = models.CharField(max_length=50) # 암호화 고려 필요하나 일단 저장
    dsnm = models.CharField(max_length=100)
    phone_num = models.CharField(max_length=20)
    telecom_gubun = models.CharField(max_length=10, blank=True, null=True)
    
    # 결과
    result = models.BooleanField(default=False) # 인증 성공 여부
    response_msg = models.TextField(blank=True, null=True) # 응답 메시지 저장
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.dsnm} - {self.created_at}"
