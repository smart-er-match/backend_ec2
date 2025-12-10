from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    SignupView, LoginView, ParamedicAuthView, KakaoLoginView, NaverLoginView, signupuu,
    ProfileUpdateView, ChangePasswordView, FindEmailView, SendAuthCodeView, 
    VerifyAuthCodeView, ResetPasswordView
)

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('signup/uu/', signupuu, name='signupuu'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('paramedic/apply/', ParamedicAuthView.as_view(), name='paramedic_apply'),
    path('social/kakao/', KakaoLoginView.as_view(), name='kakao_login'),
    path('social/naver/', NaverLoginView.as_view(), name='naver_login'),
    
    # New Accounts URLs
    path('profile/update/', ProfileUpdateView.as_view(), name='profile_update'),
    path('password/change/', ChangePasswordView.as_view(), name='password_change'),
    path('find/email/', FindEmailView.as_view(), name='find_email'),
    path('find/password/send/', SendAuthCodeView.as_view(), name='send_auth_code'),
    path('find/password/verify/', VerifyAuthCodeView.as_view(), name='verify_auth_code'),
    path('find/password/reset/', ResetPasswordView.as_view(), name='reset_password'),
]