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
    SendAuthCodeSerializer, VerifyAuthCodeSerializer, ResetPasswordSerializer,
    TokenApplicationSerializer
)
from .models import ParamedicAuthHistory, EmailVerification, UserLog, TokenApplication
import requests
import random
import uuid
import os
import threading
from datetime import timedelta
from django.core.mail import send_mail

class EmailThread(threading.Thread):
    def __init__(self, subject, body, from_email, recipient_list, fail_silently, html_message):
        self.subject = subject
        self.body = body
        self.from_email = from_email
        self.recipient_list = recipient_list
        self.fail_silently = fail_silently
        self.html_message = html_message
        threading.Thread.__init__(self)

    def run(self):
        send_mail(
            self.subject,
            self.body,
            self.from_email,
            self.recipient_list,
            self.fail_silently,
            html_message=self.html_message
        )

def send_mail_async(subject, body, from_email, recipient_list, fail_silently=False, html_message=None):
    EmailThread(subject, body, from_email, recipient_list, fail_silently, html_message).start()


User = get_user_model()

class TokenApplicationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 이미 승인된 유저인지 체크
        if request.user.token_status == 3:
             return Response({"result": False, "message": "이미 토큰이 발급된 사용자입니다."}, status=status.HTTP_400_BAD_REQUEST)
        
        # 이미 신청하여 심사 중인 경우 체크
        if request.user.token_status == 1:
             return Response({"result": False, "message": "현재 심사 중인 신청 내역이 있습니다."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TokenApplicationSerializer(data=request.data)
        if serializer.is_valid():
            application = serializer.save(user=request.user)
            
            # 유저 상태 업데이트: 1 (진행 중)
            request.user.token_status = 1
            request.user.save()
            
            # 관리자용 승인/반려 링크 (프론트엔드 페이지로 이동)
            # 프론트엔드에서 해당 페이지에 접속 시 API로 POST 요청을 보내야 함
            base_url = "https://www.smart-er-match.shop/admin/token/process"
            approval_link = f"{base_url}?mode=approve&key={application.verification_token}"
            reject_link = f"{base_url}?mode=reject&key={application.verification_token}"
            
            subject = f"[API Token 신청] {request.user.name} ({request.user.email})"
            
            # HTML 메시지 (버튼 2개)
            html_message = f"""
            <h2>새로운 API 토큰 신청이 접수되었습니다.</h2>
            <p><strong>신청자:</strong> {request.user.name} ({request.user.email})</p>
            <p><strong>활용목적:</strong> {application.purpose}</p>
            <p><strong>상세내용:</strong> {application.details}</p>
            <p><strong>상업목적 여부:</strong> {'예' if application.is_commercial else '아니오'}</p>
            <br>
            <div style="display: flex; gap: 10px;">
                <a href="{approval_link}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px; margin-right: 10px;">✅ 승인하기</a>
                <a href="{reject_link}" style="background-color: #f44336; color: white; padding: 14px 20px; text-decoration: none; border-radius: 4px;">❌ 반려하기</a>
            </div>
            """
            
            send_mail_async(
                subject,
                "HTML 메일을 확인해주세요.", # Plain text fallback
                settings.EMAIL_HOST_USER,
                [settings.EMAIL_HOST_USER], # 받는 사람: 관리자
                fail_silently=False,
                html_message=html_message
            )

            return Response({
                "result": True, 
                "message": "신청이 완료되었습니다. 관리자 심사 대기 중입니다.",
                "user": UserSerializer(request.user).data
            }, status=status.HTTP_201_CREATED)
        return Response({"result": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class TokenSuccessView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.data.get('key')
        if not token:
            return Response({"result": False, "message": "Key is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            application = TokenApplication.objects.get(verification_token=token)
        except (TokenApplication.DoesNotExist, ValueError, TypeError):
            return Response({"result": False, "message": "유효하지 않은 토큰입니다."}, status=status.HTTP_404_NOT_FOUND)
        
        user = application.user
        
        if application.is_approved:
             return Response({"result": True, "message": "이미 승인된 신청입니다."}, status=status.HTTP_200_OK)
        
        # 1. 승인 처리
        application.is_approved = True
        application.save()
        
        # 2. 서비스 키 생성 및 유저 상태 업데이트
        new_service_key = uuid.uuid4().hex
        user.service_key = new_service_key
        user.token_status = 3
        user.remaining_requests = 1000
        user.save()
        
        # 3. 유저에게 승인 이메일 발송
        subject = "[Smart ER-Match] API 토큰 발급 완료 안내"
        html_message = f"""
            <h2>안녕하세요, {user.name}님.</h2>
            <p>신청하신 API 토큰 발급이 <strong>승인</strong>되었습니다.</p>
            <hr>
            <p><strong>발급된 Service Key:</strong> <code style="background-color: #eee; padding: 5px;">{new_service_key}</code></p>
            <p>이제 해당 키를 사용하여 API 서비스를 이용하실 수 있습니다.</p>
            <p>감사합니다.</p>
            """
        send_mail_async(
            subject,
            f"승인되었습니다. Key: {new_service_key}",
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=True,
            html_message=html_message
        )
        
        return Response({"result": True, "message": "승인이 완료되었습니다. 유저에게 키를 발송했습니다."}, status=status.HTTP_200_OK)

class TokenRejectView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        print(f"DEBUG: TokenRejectView called. Data: {request.data}") # 요청 데이터 확인
        token = request.data.get('key')
        if not token:
            print("DEBUG: Key is missing.")
            return Response({"result": False, "message": "Key is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            application = TokenApplication.objects.get(verification_token=token)
            print(f"DEBUG: Application found: {application}")
        except (TokenApplication.DoesNotExist, ValueError, TypeError) as e:
            print(f"DEBUG: Application lookup failed: {e}")
            return Response({"result": False, "message": "유효하지 않은 토큰입니다."}, status=status.HTTP_404_NOT_FOUND)
        
        user = application.user
        reason = request.data.get('message', '관리자 사유 미입력')
        print(f"DEBUG: Rejection reason: {reason}")

        user.token_status = 2
        user.service_key = None
        user.save()
        print("DEBUG: User status updated to 2.")
        
        subject = "[Smart ER-Match] API 토큰 신청 반려 안내"
        html_message = f"""
            <h2>안녕하세요, {user.name}님.</h2>
            <p>죄송합니다. 신청하신 API 토큰 발급이 <strong>반려</strong>되었습니다.</p>
            <hr>
            <p><strong>반려 사유:</strong> {reason}</p>
            <p>내용을 보완하여 다시 신청해 주시기 바랍니다.</p>
            """
        send_mail_async(
            subject,
            f"반려되었습니다. 사유: {reason}",
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=True,
            html_message=html_message
        )

        return Response({"result": True, "message": "반려 처리가 완료되었습니다."}, status=status.HTTP_200_OK)

class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        # 중복 가입 확인 로직
        user_data = serializer.data
        name = request.data.get('name')
        birth_date = request.data.get('birth_date')
        
        duplicate_count = 0
        if name and birth_date:
            duplicate_count = User.objects.filter(
                name=name, 
                birth_date=birth_date, 
                sign_kind=User.SignKind.EMAIL
            ).count()
        
        user_data['is_multiple_accounts'] = duplicate_count >= 3
        
        return Response(user_data, status=status.HTTP_201_CREATED, headers=headers)

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

        if user.is_withdrawn:
            return Response({
                'error': 'Withdrawn account', 
                'error_type': 'withdrawn_user',
                'message': f'탈퇴한 계정입니다. (탈퇴일: {user.withdrawn_at.strftime("%Y-%m-%d")})'
            }, status=status.HTTP_403_FORBIDDEN)

        if not user.check_password(password):
            return Response({'error': 'Invalid Credentials', 'error_type': 'false_password'}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        
        # 자동 로그인 처리
        auto_login = request.data.get('auto_login', False)
        if auto_login == True or auto_login == 'true' or auto_login == 'True':
            refresh.set_exp(lifetime=timedelta(days=30))

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
                        user.remaining_requests = -1
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

    def patch(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            UserLog.objects.create(user=user, action_type='PROFILE_UPDATE', details=str(serializer.validated_data))
            return Response({"result": True, "user": UserSerializer(user).data}, status=status.HTTP_200_OK)
        return Response({"result": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ProfileDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.is_withdrawn = True
        user.withdrawn_at = timezone.now()
        user.is_active = False  # 로그인 불가 처리
        user.save()
        
        # 탈퇴 로그 기록
        UserLog.objects.create(
            user=user, 
            action_type='WITHDRAWAL', 
            details=f"User withdrew at {user.withdrawn_at}"
        )
        
        return Response({"result": True, "message": "회원 탈퇴가 완료되었습니다."}, status=status.HTTP_200_OK)

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.sign_kind != User.SignKind.EMAIL:
            return Response({"result": False, "message": "카카오/네이버 유저는 비밀번호를 변경할 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)

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
            
            # 탈퇴하지 않은 유저만 조회
            users = User.objects.filter(
                name=name, 
                birth_date=birth_date, 
                sign_kind=User.SignKind.EMAIL,
                is_withdrawn=False
            )
            
            if users.exists():
                found_emails = []
                for user in users:
                    email = user.email
                    try:
                        local, domain = email.split('@')
                        if len(local) > 2:
                            masked_local = local[:2] + '*' * (len(local) - 2)
                        else:
                            masked_local = local
                        masked_email = f"{masked_local}@{domain}"
                        found_emails.append(masked_email)
                    except:
                        continue

                is_multiple_accounts = users.count() >= 3

                return Response({
                    "result": True, 
                    "emails": found_emails,
                    "is_multiple_accounts": is_multiple_accounts
                }, status=status.HTTP_200_OK)
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
        birth_date = serializer.validated_data['birth_date']
        
        # 1. 이메일 가입자 우선 조회 (탈퇴자 제외)
        user = User.objects.filter(
            email=email, 
            sign_kind=User.SignKind.EMAIL,
            is_withdrawn=False
        ).first()
        
        if user:
            # 생년월일 체크
            if user.birth_date != birth_date:
                return Response({"result": False, "message": "사용자 정보가 일치하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)
        else:
            # 2. 소셜 가입자 확인 또는 탈퇴한 회원 확인
            full_user = User.objects.filter(email=email).first()
            if full_user:
                if full_user.is_withdrawn:
                    return Response({"result": False, "message": "탈퇴한 계정입니다."}, status=status.HTTP_403_FORBIDDEN)
                if full_user.sign_kind != User.SignKind.EMAIL:
                    return Response({"result": False, "message": "카카오/네이버 유저는 비밀번호를 찾을 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)
            
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

        send_mail_async(
            '[Smart ER-Match] 비밀번호 찾기 인증번호',
            f'인증번호는 [{code}] 입니다. 5분 안에 입력해주세요.',
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False,
        )
        return Response({"result": True, "message": "인증번호가 발송되었습니다."}, status=status.HTTP_200_OK)

class VerifyAuthCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyAuthCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        
        # 이메일 가입자 확인 (탈퇴자 제외)
        user = User.objects.filter(
            email=email, 
            sign_kind=User.SignKind.EMAIL,
            is_withdrawn=False
        ).first()
        if not user:
            full_user = User.objects.filter(email=email).first()
            if full_user and full_user.is_withdrawn:
                 return Response({"result": False, "message": "탈퇴한 계정입니다."}, status=status.HTTP_403_FORBIDDEN)
            if full_user:
                return Response({"result": False, "message": "카카오/네이버 유저입니다."}, status=status.HTTP_403_FORBIDDEN)
            return Response({"result": False, "message": "사용자를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        try:
            record = EmailVerification.objects.get(email=email)
            
            if timezone.now() - record.last_sent_at > timedelta(minutes=5):
                return Response({"result": False, "message": "인증번호 유효 시간이 만료되었습니다."}, status=status.HTTP_400_BAD_REQUEST)
            
            if record.code == code:
                record.is_verified = True
                record.save()
                
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
            birth_date = serializer.validated_data['birth_date']
            new_password = serializer.validated_data['new_password']
            
            # 이메일 가입자 확인 (탈퇴자 제외)
            user = User.objects.filter(
                email=email, 
                sign_kind=User.SignKind.EMAIL,
                is_withdrawn=False
            ).first()
            
            if user:
                # 생년월일 체크
                if user.birth_date != birth_date:
                    return Response({"result": False, "message": "사용자 정보가 일치하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

                if not user.can_password_edit:
                    return Response({"result": False, "message": "비밀번호 변경 권한이 없습니다. 먼저 인증을 진행해주세요."}, status=status.HTTP_403_FORBIDDEN)
                
                user.set_password(new_password)
                user.can_password_edit = False
                user.save()
                
                UserLog.objects.create(user=user, action_type='PASSWORD_RESET', details="Password reset via email auth")
                
                return Response({"result": True, "message": "비밀번호가 재설정되었습니다."}, status=status.HTTP_200_OK)
            else:
                # 소셜 가입자 또는 탈퇴한 회원 확인
                full_user = User.objects.filter(email=email).first()
                if full_user:
                    if full_user.is_withdrawn:
                        return Response({"result": False, "message": "탈퇴한 계정입니다."}, status=status.HTTP_403_FORBIDDEN)
                    return Response({"result": False, "message": "카카오/네이버 유저는 비밀번호를 재설정할 수 없습니다."}, status=status.HTTP_403_FORBIDDEN)
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
        redirect_uri = os.getenv("KAKAO_REDIRECT_URI", "http://13.125.206.129/auth/kakao/callback")

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
            if user.is_withdrawn:
                return Response({
                    "error": "Withdrawn account", 
                    "error_type": "withdrawn_user",
                    "message": f"탈퇴한 계정입니다. (탈퇴일: {user.withdrawn_at.strftime('%Y-%m-%d')})"
                }, status=status.HTTP_403_FORBIDDEN)
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
        
        # 자동 로그인 처리
        auto_login = request.data.get('auto_login', False)
        if auto_login in [True, 'true', 'True']:
            refresh.set_exp(lifetime=timedelta(days=30))

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
        print(f"DEBUG: Naver User Info: {user_info}") # 디버깅용 로그 추가
        naver_id = user_info.get("id")
        if not naver_id:
            return Response({"error": "Naver user id is required"}, status=status.HTTP_400_BAD_REQUEST)

        email = user_info.get("email")
        name = user_info.get("name")
        mobile = user_info.get("mobile")
        birthyear = user_info.get("birthyear")
        birthday = user_info.get("birthday")
        gender_raw = user_info.get("gender", "")

        username = str(naver_id)
        normalized_email = email if email else f"naver_{naver_id}@naver.local"

        birth_date = None
        if birthyear and birthday:
            birth_date = f"{birthyear}-{birthday}"

        # 성별 처리 강화 (M, F 외에는 저장 안함)
        gender = None
        if gender_raw in ['M', 'F']:
            gender = gender_raw

        try:
            user = User.objects.get(naver_id=str(naver_id))
            if user.is_withdrawn:
                return Response({
                    "error": "Withdrawn account", 
                    "error_type": "withdrawn_user",
                    "message": f"탈퇴한 계정입니다. (탈퇴일: {user.withdrawn_at.strftime('%Y-%m-%d')})"
                }, status=status.HTTP_403_FORBIDDEN)
        except User.DoesNotExist:
            user = User.objects.create(
                username=uuid.uuid4(),
                email=normalized_email,
                sign_kind=User.SignKind.NAVER,
                naver_id=str(naver_id),
                name=name if name else "",
                phone_number=mobile if mobile else "",
                birth_date=birth_date,
                gender=gender,
            )
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)
        
        # 자동 로그인 처리
        auto_login = request.data.get('auto_login', False)
        if auto_login in [True, 'true', 'True']:
            refresh.set_exp(lifetime=timedelta(days=30))

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })

class GoogleLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response({"error": "Code is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Access Token 요청
        token_url = "https://oauth2.googleapis.com/token"
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = "https://www.smart-er-match.shop/auth/google/callback"

        token_data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        token_res = requests.post(token_url, data=token_data)
        if token_res.status_code != 200:
            return Response({"error": "Failed to get token from Google", "details": token_res.json()}, status=status.HTTP_400_BAD_REQUEST)

        access_token = token_res.json().get("access_token")

        # 2. 사용자 정보 요청
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info_res = requests.get(user_info_url, headers=headers)

        if user_info_res.status_code != 200:
            return Response({"error": "Failed to get user info from Google"}, status=status.HTTP_400_BAD_REQUEST)

        user_info = user_info_res.json()
        google_id = str(user_info.get("id"))
        email = user_info.get("email")
        name = user_info.get("name", "")

        try:
            user = User.objects.get(google_id=google_id)
            if user.is_withdrawn:
                return Response({
                    "error": "Withdrawn account", 
                    "error_type": "withdrawn_user",
                    "message": f"탈퇴한 계정입니다. (탈퇴일: {user.withdrawn_at.strftime('%Y-%m-%d')})"
                }, status=status.HTTP_403_FORBIDDEN)
        except User.DoesNotExist:
            normalized_email = email if email else f"google_{google_id}@google.local"
            user = User.objects.create(
                username=uuid.uuid4(),
                email=normalized_email,
                sign_kind=User.SignKind.GOOGLE,
                google_id=google_id,
                name=name,
            )
            user.set_unusable_password()
            user.save()

        refresh = RefreshToken.for_user(user)
        
        # 자동 로그인 처리
        auto_login = request.data.get('auto_login', False)
        if auto_login in [True, 'true', 'True']:
            refresh.set_exp(lifetime=timedelta(days=30))

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })

class MyPageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response({
            "result": True,
            "user": serializer.data
        }, status=status.HTTP_200_OK)
