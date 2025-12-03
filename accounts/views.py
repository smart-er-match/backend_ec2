from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db import models
from .serializers import SignupSerializer, UserSerializer
import uuid

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

# 로컬(username) 중복 체크: 이메일 회원(sign_kind=EMAIL)만 확인

@api_view(['GET'])
def signupuu(request):
        username = request.query_params.get("username")
        if not username:
            # username 누락 시에도 bool_uu는 False로 응답한다.
            return Response({"bool_uu": False, "error": "username is required"}, status=status.HTTP_200_OK)

        # 일반 회원(email sign_kind만)에서 이메일/아이디 중복을 확인한다.
        is_available = not User.objects.filter(
            email=username,
            sign_kind=User.SignKind.EMAIL
        ).exists()
        return Response({"bool_uu": is_available})


class ParamedicAuthView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .serializers import ParamedicAuthSerializer, UserSerializer
        from .models import ParamedicAuthHistory
        from django.conf import settings
        import requests

        # 1. 입력 데이터 검증
        serializer = ParamedicAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"result": False, "message": "Validation Error", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        jumin = data['JUMIN']
        dsnm = data['DSNM']
        phone_num = data['PHONENUM']
        
        # 2. 주민번호 파싱 (생년월일, 성별)
        # 7자리: YYMMDD + G
        yy = jumin[:2]
        mm = jumin[2:4]
        dd = jumin[4:6]
        gender_digit = jumin[6]

        # 1900년대 vs 2000년대
        if gender_digit in ['1', '2']:
            full_year = f"19{yy}"
            gender_code = 'M' if gender_digit == '1' else 'F'
        else: # 3, 4
            full_year = f"20{yy}"
            gender_code = 'M' if gender_digit == '3' else 'F'
        
        birth_date = f"{full_year}-{mm}-{dd}"

        # 3. 유저 정보 업데이트 (비어있는 필드 채우기)
        user = request.user
        user.name = dsnm
        user.phone_number = phone_num
        user.birth_date = birth_date
        user.gender = gender_code
        user.save()

        # 4. 파라메트릭 인증 요청 이력 저장
        auth_history = ParamedicAuthHistory.objects.create(
            user=user,
            login_option=data['LOGINOPTION'],
            jumin=jumin, # 7자리 저장
            dsnm=dsnm,
            phone_num=phone_num,
            telecom_gubun=data.get('TELECOMGUBUN')
        )

        # 5. AWS Lambda API 호출
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

        # Lambda로 보낼 때는 프론트에서 받은 그대로 전송 (주민번호 7자리 포함)
        payload = {
            "LOGINOPTION": data['LOGINOPTION'],
            "JUMIN": jumin,
            "DSNM": dsnm,
            "PHONENUM": phone_num,
            "TELECOMGUBUN": data.get('TELECOMGUBUN')
        }

        try:
            # verify=False 옵션 없이 호출 (혹은 필요시 추가)
            response = requests.post(lambda_url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                resp_data = response.json()
                
                # 성공 여부 체크
                if resp_data.get('result') == 'SUCCESS' and resp_data.get('data', {}).get('RESULT') == 'SUCCESS':
                    license_list = resp_data['data'].get('LICENSELIST', [])
                    
                    if license_list:
                        license_info = license_list[0]
                        
                        # 유저 정보 업데이트 (Role, License)
                        user.role = True 
                        user.license_kind = license_info.get('LICENSEKIND')
                        user.license_number = license_info.get('LICENSENUM')
                        user.license_date = license_info.get('LICENSEDATE')
                        user.is_license_verified = True
                        user.save()

                        # 이력 업데이트
                        auth_history.result = True
                        auth_history.response_msg = "Success"
                        auth_history.save()

                        # 성공 응답 (변경된 유저 정보 포함)
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


import os
import requests


class KakaoLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response({"error": "Code is required"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. 토큰 발급
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

        # 2. 유저 정보 가져오기
        user_info_url = "https://kapi.kakao.com/v2/user/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info_res = requests.get(user_info_url, headers=headers)

        if user_info_res.status_code != 200:
            return Response({"error": "Failed to get user info"}, status=status.HTTP_400_BAD_REQUEST)

        user_info = user_info_res.json()
        kakao_id = str(user_info.get("id")) # 문자로 확실하게 변환
        kakao_account = user_info.get("kakao_account", {})
        profile = kakao_account.get("profile", {}) or {}

        email = kakao_account.get("email")
        nickname = profile.get("nickname", "")

        # 3. 로그인/회원가입 로직 (수정됨)
        try:
            # ★ 중요: username이 아니라 고유한 kakao_id로 찾습니다.
            user = User.objects.get(kakao_id=kakao_id)
        except User.DoesNotExist:
            # 없으면 새로 생성 (이메일, 닉네임 등 설정)
            normalized_email = email if email else f"kakao_{kakao_id}@kakao.local"
            
            user = User.objects.create(
                username=uuid.uuid4(), # ★ 중요: 중복 방지를 위해 UUID 사용
                email=normalized_email,
                sign_kind=User.SignKind.KAKAO,
                kakao_id=kakao_id,
                name=nickname if nickname else "Unknown",
            )
            user.set_unusable_password() # 비밀번호 사용 불가 처리
            user.save()

        # 4. 토큰 발급
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
        birthday = user_info.get("birthday")  # MM-DD
        gender = user_info.get("gender", "")

        username = str(naver_id)  # username = 네이버 id
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




