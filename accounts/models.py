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
    license_date = models.CharField(max_length=20, blank=True, null=True)
    is_license_verified = models.BooleanField(default=False)

    # 비밀번호 변경 권한 (비밀번호 찾기 인증 성공 시 True)
    can_password_edit = models.BooleanField(default=False)

    # 위치 정보 (UserLocationLog 최신값 캐싱용 또는 기본값)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    radius = models.IntegerField(default=10)

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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_histories')
    login_option = models.CharField(max_length=10)
    jumin = models.CharField(max_length=50)
    dsnm = models.CharField(max_length=100)
    phone_num = models.CharField(max_length=20)
    telecom_gubun = models.CharField(max_length=10, blank=True, null=True)
    result = models.BooleanField(default=False)
    response_msg = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.dsnm} - {self.created_at}"

class EmailVerification(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True) # 생성 시간 (만료 체크용)
    send_count = models.IntegerField(default=1) # 하루 발송 횟수
    last_sent_at = models.DateTimeField(auto_now=True) # 마지막 발송 시간 (15초 제한용)

class UserLog(models.Model):
    """
    회원 정보 변경 이력 로그
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logs')
    action_type = models.CharField(max_length=50) # 'PROFILE_UPDATE', 'PASSWORD_CHANGE'
    details = models.TextField(blank=True) # 변경 상세 내용
    created_at = models.DateTimeField(auto_now_add=True)