from django.urls import path
from .views import UserLocationView, GeneralSymptomView, ReviewView, ReviewDetailView, CommentView, CommentDetailView

urlpatterns = [
    path('user/location/', UserLocationView.as_view(), name='user_location_log'),
    path('general/symptom/', GeneralSymptomView.as_view(), name='general_symptom'),
    
    # Review URLs
    path('reviews/<str:hpid>/', ReviewView.as_view(), name='review_list_create'), # GET: list, POST: create
    path('reviews/detail/<int:review_id>/', ReviewDetailView.as_view(), name='review_detail'), # PUT: update, DELETE: delete
    
    # Comment URLs
    path('comments/<int:review_id>/', CommentView.as_view(), name='comment_create'), # POST: create
    path('comments/detail/<int:comment_id>/', CommentDetailView.as_view(), name='comment_detail'), # PUT: update, DELETE: delete
]
