from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ParamedicAuthHistory, TokenApplication
import re

User = get_user_model()

class TokenApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TokenApplication
        fields = ['id', 'user', 'purpose', 'details', 'is_commercial', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    bookmarked_hospitals = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'name',
            'phone_number',
            'birth_date',
            'gender',
            'role',
            'sign_kind',
            'kakao_id',
            'naver_id',
            'license_kind',
            'license_number',
            'license_date',
            'is_license_verified',
            'latitude',
            'longitude',
            'location',
            'radius',
            'service_key',
            'token_status',
            'is_withdrawn',
            'withdrawn_at',
            'remaining_requests',
            'bookmarked_hospitals'
        ]

    def get_bookmarked_hospitals(self, obj):
        from hospitals.serializers import HospitalListSerializer
        from hospitals.models import Hospital
        from django.db.models import Avg, Count
        
        # 북마크된 병원 객체들을 가져오며 필요한 정보(평점, 리뷰수 등)를 계산(annotate)
        hospitals = Hospital.objects.filter(bookmarked_by__user=obj).annotate(
            average_rating=Avg('reviews__rating'),
            review_count=Count('reviews')
        ).prefetch_related('realtime_status', 'bookmarked_by')
        
        return HospitalListSerializer(hospitals, many=True, context=self.context).data

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=20,
        error_messages={
            'min_length': '비밀번호는 8자 이상이어야 합니다.',
            'max_length': '비밀번호는 20자 이하여야 합니다.',
        },
    )
    phone_number = serializers.RegexField(
        regex=r'^\d{11}$',
        min_length=11,
        max_length=11,
        error_messages={'invalid': '전화번호는 하이픈 없이 숫자 11자리여야 합니다.'},
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    birth_date = serializers.DateField()
    gender = serializers.CharField(max_length=1)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'name',
            'phone_number',
            'birth_date',
            'gender',
        ]
        extra_kwargs = {
            'username': {'required': True, 'allow_blank': False},
            'email': {'required': False, 'allow_blank': True},
            'name': {'required': True, 'allow_blank': False},
            'phone_number': {'required': True, 'allow_blank': False, 'allow_null': False},
            'birth_date': {'required': True, 'allow_null': False},
            'gender': {'required': True, 'allow_blank': False},
        }

    def validate(self, attrs):
        for field in ['name', 'phone_number', 'password', 'gender']:
            if not str(attrs.get(field, '')).strip():
                raise serializers.ValidationError({field: 'This field is required.'})
        if not attrs.get('birth_date'):
            raise serializers.ValidationError({'birth_date': 'This field is required.'})

        email_value = attrs.get('email') or attrs.get('username')
        if not email_value:
            raise serializers.ValidationError({'email': '이메일이 필요합니다.'})
        attrs['email'] = email_value
        attrs['username'] = email_value

        password = attrs.get('password')
        if password:
            if not (8 <= len(password) <= 20):
                raise serializers.ValidationError({'password': '비밀번호는 8자 이상 20자 이하여야 합니다.'})
            if not re.search(r'[A-Za-z]', password):
                raise serializers.ValidationError({'password': '비밀번호에는 영문이 포함되어야 합니다.'})
            if not re.search(r'\d', password):
                raise serializers.ValidationError({'password': '비밀번호에는 숫자가 포함되어야 합니다.'})
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise serializers.ValidationError({'password': '비밀번호에는 특수문자가 포함되어야 합니다.'})

        if User.objects.filter(email=attrs['email'], sign_kind=User.SignKind.EMAIL).exists():
            raise serializers.ValidationError({'email': '이미 가입된 이메일입니다.'})

        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            name=validated_data['name'],
            phone_number=validated_data['phone_number'],
            birth_date=validated_data['birth_date'],
            gender=validated_data['gender'],
            sign_kind=User.SignKind.EMAIL,
        )
        return user

class ParamedicAuthSerializer(serializers.Serializer):
    LOGINOPTION = serializers.CharField(required=True)
    JUMIN = serializers.CharField(required=True, min_length=7, max_length=7)
    DSNM = serializers.CharField(required=True, min_length=2, max_length=5)
    PHONENUM = serializers.CharField(required=True, min_length=11, max_length=11)
    TELECOMGUBUN = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        login_option = attrs.get('LOGINOPTION')
        telecom_gubun = attrs.get('TELECOMGUBUN')
        jumin = attrs.get('JUMIN')
        phone_num = attrs.get('PHONENUM')

        if login_option == '3' and not telecom_gubun:
            raise serializers.ValidationError({"TELECOMGUBUN": "통신사 로그인 시 통신사 구분은 필수입니다."})

        if not jumin.isdigit():
            raise serializers.ValidationError({"JUMIN": "주민등록번호는 숫자여야 합니다."})
        
        last_digit = jumin[6]
        if last_digit not in ['1', '2', '3', '4']:
             raise serializers.ValidationError({"JUMIN": "주민등록번호 뒷자리가 올바르지 않습니다. (1, 2, 3, 4 중 하나)"})

        if not phone_num.isdigit():
            raise serializers.ValidationError({"PHONENUM": "휴대폰 번호는 숫자여야 합니다."})

        return attrs

class ProfileUpdateSerializer(serializers.ModelSerializer):
    phone_number = serializers.RegexField(
        regex=r'^\d{11}$',
        min_length=11,
        max_length=11,
        error_messages={'invalid': '전화번호는 하이픈 없이 숫자 11자리여야 합니다.'},
        required=False
    )
    name = serializers.CharField(required=False, allow_blank=False)
    gender = serializers.CharField(required=False, allow_blank=False)

    class Meta:
        model = User
        fields = ['name', 'phone_number', 'gender']

    def validate(self, attrs):
        for field in ['name', 'phone_number', 'gender']:
            if field in attrs:
                val = attrs.get(field)
                if not str(val).strip():
                    raise serializers.ValidationError({field: 'This field cannot be blank.'})
        return attrs

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "새 비밀번호가 일치하지 않습니다."})
        return attrs

class FindEmailSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    birth_date = serializers.DateField(required=True)

class SendAuthCodeSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    birth_date = serializers.DateField(required=True) # 생년월일 추가

class VerifyAuthCodeSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, min_length=6, max_length=6)

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    birth_date = serializers.DateField(required=True) # 생년월일 추가
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "새 비밀번호가 일치하지 않습니다."})
        return attrs
