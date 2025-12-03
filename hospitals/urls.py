from django.urls import path
from .views import UserLocationView, GeneralSymptomView

urlpatterns = [
    path('user/location/', UserLocationView.as_view(), name='user_location_log'),
    path('general/symptom/', GeneralSymptomView.as_view(), name='general_symptom'),
]