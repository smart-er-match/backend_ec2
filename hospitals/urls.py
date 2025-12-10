from django.urls import path
from .views import UserLocationView, GeneralSymptomView, HospitalListView, ReviewView, ReviewDetailView, CommentView, CommentDetailView, ChatbotView, BookMarkView, ChatbotFinishView

urlpatterns = [
    path('user/location/', UserLocationView.as_view(), name='user_location_log'),
    path('general/symptom/', GeneralSymptomView.as_view(), name='general_symptom'),
    path('chatbot/', ChatbotView.as_view(), name='chatbot'),
    path('chatbot/finish/', ChatbotFinishView.as_view(), name='chatbot_finish'),
    path('bookmark/<str:hpid>/', BookMarkView.as_view(), name='hospital_bookmark'),
    path('list/', HospitalListView.as_view(), name='hospital_list'),
    path('reviews/<str:hpid>/', ReviewView.as_view(), name='review_list_create'),
    path('reviews/detail/<int:review_id>/', ReviewDetailView.as_view(), name='review_detail'),
    path('comments/<int:review_id>/', CommentView.as_view(), name='comment_create'),
    path('comments/detail/<int:comment_id>/', CommentDetailView.as_view(), name='comment_detail'),
]