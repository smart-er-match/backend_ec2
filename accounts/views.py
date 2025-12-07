from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from .serializers import (
    SignupSerializer, UserSerializer, ParamedicAuthSerializer, 
    ProfileUpdateSerializer, ChangePasswordSerializer, FindEmailSerializer,
    SendAuthCodeSerializer, VerifyAuthCodeSerializer, ResetPasswordSerializer
)
from .models import ParamedicAuthHistory, EmailVerification, UserLog
import requests
import random
import uuid
import os
from datetime import timedelta

User = get_user_model()

class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get('email') or request.data.get('username')
        password = request.data.get('password')
        if not identifier or not password:
            return Response({'error': 'Username and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(
            email=identifier,
            sign_kind=User.SignKind.EMAIL,
        ).order_by('date_joined').first()
        if not user:
            return Response({'error': 'Invalid Credentials', 'error_type': 'undefined_email'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({'error': 'Invalid Credentials', 'error_type': 'false_password'}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
            'error_type': ''
        })

@api_view(['GET'])
def signupuu(request):
        username = request.query_params.get("username")
        if not username:
            return Response({"bool_uu": False, "error": "username is required"}, status=status.HTTP_200_OK)

        is_available = not User.objects.filter(
            email=username,
            sign_kind=User.SignKind.EMAIL
        ).exists()
        return Response({"bool_uu": is_available})

class ParamedicAuthView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ParamedicAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"result": False, "message": "Validation Error", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        jumin = data['JUMIN']
        dsnm = data['DSNM']
        phone_num = data['PHONENUM']
        
        yy = jumin[:2]
        mm = jumin[2:4]
        dd = jumin[4:6]
        gender_digit = jumin[6]

        if gender_digit in ['1', '2']:
            full_year = f"19{yy}"
            gender_code = 'M' if gender_digit == '1' else 'F'
        else:
            full_year = f"20{yy}"
            gender_code = 'M' if gender_digit == '3' else 'F'
        
        birth_date = f"{full_year}-{mm}-{dd}"

        user = request.user
        updated = False
        if not user.name:
            user.name = dsnm
            updated = True
        if not user.phone_number:
            user.phone_number = phone_num
            updated = True
        if not user.birth_date:
            user.birth_date = birth_date
            updated = True
        if not user.gender:
            user.gender = gender_code
            updated = True
        
        if updated:
            user.save()

        auth_history = ParamedicAuthHistory.objects.create(
            user=user,
            login_option=data['LOGINOPTION'],
            jumin=jumin,
            dsnm=dsnm,
            phone_num=phone_num,
            telecom_gubun=data.get('TELECOMGUBUN')
        )

        lambda_url = getattr(settings, 'PARAMETIC_URI', None)
        lambda_token = getattr(settings, 'PARAMETIC_TOKEN', None)

        if not lambda_url or not lambda_token:
            auth_history.response_msg = "Server Config Error"
            auth_history.save()
            return Response({"result": False, "message": "Server configuration error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": lambda_token
        }

        payload = {
            "LOGINOPTION": data['LOGINOPTION'],
            "JUMIN": jumin,
            "DSNM": dsnm,
            "PHONENUM": phone_num,
            "TELECOMGUBUN": data.get('TELECOMGUBUN')
        }

        try:
            response = requests.post(lambda_url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get('result') == 'SUCCESS' and resp_data.get('data', {}).get('RESULT') == 'SUCCESS':
                    license_list = resp_data['data'].get('LICENSELIST', [])
                    if license_list:
                        license_info = license_list[0]
                        user.role = True 
                        user.license_kind = license_info.get('LICENSEKIND')
                        user.license_number = license_info.get('LICENSENUM')
                        user.license_date = license_info.get('LICENSEDATE')
                        user.is_license_verified = True
                        user.save()

                        auth_history.result = True
                        auth_history.response_msg = "Success"
                        auth_history.save()

                        return Response({
                            "result": True, 
                            "message": "Verification successful",
                            "user": UserSerializer(user).data
                        }, status=status.HTTP_200_OK)
                    else:
                        auth_history.response_msg = "No license found"
                        auth_history.save()
                        return Response({"result": False, "message": "No license information found"}, status=status.HTTP_200_OK)
                else:
                    err_msg = resp_data.get('errMsg', 'Verification failed')
                    auth_history.response_msg = err_msg
                    auth_history.save()
                    return Response({"result": False, "message": err_msg}, status=status.HTTP_200_OK)
            elif response.status_code == 401:
                auth_history.response_msg = "401 Unauthorized (Lambda)"
                auth_history.save()
                return Response({"result": False, "message": "Unauthorized (External API)"}, status=status.HTTP_401_UNAUTHORIZED)
            else:
                auth_history.response_msg = f"API Error {response.status_code}"
                auth_history.save()
                return Response({"result": False, "message": f"API Error: {response.status_code}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except requests.exceptions.RequestException as e:
            auth_history.response_msg = f"Network Error: {str(e)}"
            auth_history.save()
            return Response({"result": False, "message": f"Network Error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProfileUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            UserLog.objects.create(user=user, action_type='PROFILE_UPDATE', details=str(serializer.validated_data))
            return Response({"result": True, "user": UserSerializer(user).data}, status=status.HTTP_200_OK)
        return Response({"result": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({"result": False, "message": "기존 비밀번호가 일치하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            UserLog.objects.create(user=user, action_type='PASSWORD_CHANGE', details="User initiated password change")
            return Response({"result": True, "message": "비밀번호가 변경되었습니다."}, status=status.HTTP_200_OK)
        return Response({"result": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class FindEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = FindEmailSerializer(data=request.data)
        if serializer.is_valid():
            name = serializer.validated_data['name']
            birth_date = serializer.validated_data['birth_date']
            
            users = User.objects.filter(name=name, birth_date=birth_date, sign_kind=User.SignKind.EMAIL)
            if users.exists():
                email = users.first().email
                try:
                    local, domain = email.split('@')
                    if len(local) > 2:
                        masked_local = local[:2] + '*' * (len(local) - 2)
                    else:
                        masked_local = local
                    masked_email = f"{masked_local}@{domain}"
                    return Response({"result": True, "email": masked_email}, status=status.HTTP_200_OK)
                except:
                    return Response({"result": False, "message": "이메일 형식이 올바르지 않습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({"result": False, "message": "일치하는 사용자 정보가 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"result": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class SendAuthCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendAuthCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        if not User.objects.filter(email=email, sign_kind=User.SignKind.EMAIL).exists():
            return Response({"result": False, "message": "등록되지 않은 이메일입니다."}, status=status.HTTP_404_NOT_FOUND)

        code = str(random.randint(100000, 999999))
        
        try:
            record = EmailVerification.objects.get(email=email)
            
            if record.created_at.date() == timezone.now().date():
                if record.send_count >= 5:
                    return Response({"result": False, "message": "하루 인증 요청 횟수(5회)를 초과했습니다."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            else:
                record.created_at = timezone.now()
                record.send_count = 0

            if timezone.now() - record.last_sent_at < timedelta(seconds=15):
                return Response({"result": False, "message": "잠시 후 다시 시도해주세요. (15초 제한)"}, status=status.HTTP_429_TOO_MANY_REQUESTS)

            record.code = code
            record.is_verified = False
            record.send_count += 1
            record.last_sent_at = timezone.now()
            record.save()
            
        except EmailVerification.DoesNotExist:
            EmailVerification.objects.create(email=email, code=code)

        try:
            send_mail(
                '[Smart ER-Match] 비밀번호 찾기 인증번호',
                f'인증번호는 [{code}] 입니다. 5분 안에 입력해주세요.',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            return Response({"result": True, "message": "인증번호가 발송되었습니다."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"result": False, "message": f"이메일 발송 실패: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VerifyAuthCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyAuthCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        
        try:
            record = EmailVerification.objects.get(email=email)
            
            if timezone.now() - record.last_sent_at > timedelta(minutes=5):
                return Response({"result": False, "message": "인증번호 유효 시간이 만료되었습니다."}, status=status.HTTP_400_BAD_REQUEST)
            
            if record.code == code:
                record.is_verified = True
                record.save()
                
                user = User.objects.get(email=email, sign_kind=User.SignKind.EMAIL)
                user.can_password_edit = True
                user.save()
                
                return Response({"result": True, "message": "인증되었습니다."}, status=status.HTTP_200_OK)
            else:
                return Response({"result": False, "message": "인증번호가 일치하지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
                
        except EmailVerification.DoesNotExist:
            return Response({"result": False, "message": "인증 요청 내역이 없습니다."}, status=status.HTTP_404_NOT_FOUND)

class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            new_password = serializer.validated_data['new_password']
            
            try:
                user = User.objects.get(email=email, sign_kind=User.SignKind.EMAIL)
                
                if not user.can_password_edit:
                    return Response({"result": False, "message": "비밀번호 변경 권한이 없습니다. 먼저 인증을 진행해주세요."}, status=status.HTTP_403_FORBIDDEN)
                
                user.set_password(new_password)
                user.can_password_edit = False
                user.save()
                
                UserLog.objects.create(user=user, action_type='PASSWORD_RESET', details="Password reset via email auth")
                
                return Response({"result": True, "message": "비밀번호가 재설정되었습니다."}, status=status.HTTP_200_OK)
                
            except User.DoesNotExist:
                return Response({"result": False, "message": "사용자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({"result": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class KakaoLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response({"error": "Code is required"}, status=status.HTTP_400_BAD_REQUEST)

        token_url = "https://kauth.kakao.com/oauth/token"
        client_id = os.getenv("KAKAO_OAUTH_REST_API_KEY")
        redirect_uri = os.getenv("KAKAO_REDIRECT_URI", "http://13.209.99.166/auth/kakao/callback")

        token_data = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code": code,
        }

        token_res = requests.post(token_url, data=token_data)
        if token_res.status_code != 200:
            return Response({"error": "Failed to get token", "details": token_res.json()}, status=status.HTTP_400_BAD_REQUEST)

        access_token = token_res.json().get("access_token")

        user_info_url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info_res = requests.get(user_info_url, headers=headers)

        if user_info_res.status_code != 200:
            return Response({"error": "Failed to get user info"}, status=status.HTTP_400_BAD_REQUEST)

        user_info = user_info_res.json()
        kakao_id = str(user_info.get("id"))
        kakao_account = user_info.get("kakao_account", {})
        profile = kakao_account.get("profile", {}) or {}

        email = kakao_account.get("email")
        nickname = profile.get("nickname", "")

        try:
            user = User.objects.get(kakao_id=kakao_id)
        except User.DoesNotExist:
            normalized_email = email if email else f"kakao_{kakao_id}@kakao.local"
            
            user = User.objects.create(
                username=uuid.uuid4(),
                email=normalized_email,
                sign_kind=User.SignKind.KAKAO,
                kakao_id=kakao_id,
                name=nickname if nickname else "Unknown",
            )
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })

class NaverLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = request.data.get("code")
        state = request.data.get("state", "dummy_state")
        redirect_uri = os.getenv("NAVER_REDIRECT_URI")

        if not code:
            return Response({"error": "Code is required"}, status=status.HTTP_400_BAD_REQUEST)

        token_url = "https://nid.naver.com/oauth2.0/token"
        client_id = os.getenv("NAVER_CLIENT_ID")
        client_secret = os.getenv("NAVER_CLIENT_SECRET")

        token_params = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "state": state,
        }
        if redirect_uri:
            token_params["redirect_uri"] = redirect_uri

        token_res = requests.post(token_url, data=token_params)
        token_data = token_res.json() if token_res.content else {}
        if token_res.status_code != 200 or token_data.get("error") or not token_data.get("access_token"):
            return Response(
                {
                    "error": "Failed to get token from Naver",
                    "details": token_data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_token = token_data.get("access_token")

        user_info_url = "https://openapi.naver.com/v1/nid/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info_res = requests.get(user_info_url, headers=headers)

        user_info_data = user_info_res.json() if user_info_res.content else {}
        if user_info_res.status_code != 200 or user_info_data.get("resultcode") not in ("00", "0", "SUCCESS"):
            return Response(
                {
                    "error": "Failed to get user info from Naver",
                    "details": user_info_data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_info = user_info_data.get("response", {})
        naver_id = user_info.get("id")
        if not naver_id:
            return Response({"error": "Naver user id is required"}, status=status.HTTP_400_BAD_REQUEST)

        email = user_info.get("email")
        name = user_info.get("name")
        mobile = user_info.get("mobile")
        birthyear = user_info.get("birthyear")
        birthday = user_info.get("birthday")
        gender = user_info.get("gender", "")

        username = str(naver_id)
        normalized_email = email if email else f"naver_{naver_id}@naver.local"

        birth_date = None
        if birthyear and birthday:
            birth_date = f"{birthyear}-{birthday}"

        try:
            user = User.objects.get(username=username, sign_kind=User.SignKind.NAVER)
        except User.DoesNotExist:
            user, _ = User.objects.get_or_create(
                username=username,
                email=normalized_email,
                sign_kind=User.SignKind.NAVER,
                defaults={
                    "name": name if name else "",
                    "phone_number": mobile if mobile else "",
                    "birth_date": birth_date,
                    "gender": gender if gender else "",
                    "naver_id": str(naver_id),
                },
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
        if not user.naver_id:
            user.naver_id = str(naver_id)
            user.save(update_fields=["naver_id"])

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })
