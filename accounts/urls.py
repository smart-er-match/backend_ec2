from django.urls import path
from .views import SignupView, LoginView, ParamedicAuthView, KakaoLoginView, NaverLoginView, signupuu

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('signup/uu/', signupuu, name='signupuu'),
    path('login/', LoginView.as_view(), name='login'),
    path('paramedic/apply/', ParamedicAuthView.as_view(), name='paramedic_apply'),
    path('social/kakao/', KakaoLoginView.as_view(), name='kakao_login'),
    path('social/naver/', NaverLoginView.as_view(), name='naver_login'),
]
