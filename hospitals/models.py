from django.db import models
from accounts.models import User

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Hospital(models.Model):
    hpid = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    first_address = models.CharField(max_length=50, blank=True)
    second_address = models.CharField(max_length=50, blank=True)
    third_address = models.CharField(max_length=100, blank=True)
    category_name = models.CharField(max_length=50, blank=True, null=True)
    main_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_phone = models.CharField(max_length=20, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.hpid}] {self.name}"

class Review(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hospital_reviews')
    content = models.TextField()
    rating = models.IntegerField(default=5) # 1~5점
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.hospital.name} - {self.user.name}"

class Comment(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='review_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment by {self.user.name}"

class HospitalRealtimeStatus(models.Model):
    hospital = models.OneToOneField(Hospital, on_delete=models.CASCADE, related_name='realtime_status')
    
    # 응답 XML 필드 그대로 매핑 (hv*)
    hv10 = models.CharField(max_length=10, blank=True, null=True)
    hv11 = models.CharField(max_length=10, blank=True, null=True)
    hv13 = models.IntegerField(default=0)
    hv14 = models.IntegerField(default=0)
    hv18 = models.IntegerField(default=0)
    hv2 = models.IntegerField(default=0)
    hv24 = models.IntegerField(default=0)
    hv25 = models.IntegerField(default=0)
    hv27 = models.IntegerField(default=0)
    hv28 = models.IntegerField(default=0)
    hv29 = models.IntegerField(default=0)
    hv3 = models.IntegerField(default=0)
    hv30 = models.IntegerField(default=0)
    hv31 = models.IntegerField(default=0)
    hv34 = models.IntegerField(default=0)
    hv35 = models.IntegerField(default=0)
    hv36 = models.IntegerField(default=0)
    hv38 = models.IntegerField(default=0)
    hv40 = models.IntegerField(default=0)
    hv41 = models.IntegerField(default=0)
    hv42 = models.CharField(max_length=10, blank=True, null=True)
    hv5 = models.CharField(max_length=10, blank=True, null=True)
    hv7 = models.CharField(max_length=10, blank=True, null=True)
    hvamyn = models.CharField(max_length=10, blank=True, null=True)
    hvangioayn = models.CharField(max_length=10, blank=True, null=True)
    hvcrrtayn = models.CharField(max_length=10, blank=True, null=True)
    hvctayn = models.CharField(max_length=10, blank=True, null=True)
    hvec = models.IntegerField(default=0)
    hvecmoayn = models.CharField(max_length=10, blank=True, null=True)
    hvgc = models.IntegerField(default=0)
    hvhypoayn = models.CharField(max_length=10, blank=True, null=True)
    hvidate = models.CharField(max_length=20, blank=True, null=True)
    hvincuayn = models.CharField(max_length=10, blank=True, null=True)
    hvmriayn = models.CharField(max_length=10, blank=True, null=True)
    hvncc = models.IntegerField(default=0)
    hvoc = models.IntegerField(default=0)
    hvoxyayn = models.CharField(max_length=10, blank=True, null=True)
    hvs01 = models.IntegerField(default=0)
    hvs02 = models.IntegerField(default=0)
    hvs03 = models.IntegerField(default=0)
    hvs04 = models.IntegerField(default=0)
    hvs05 = models.IntegerField(default=0)
    hvs06 = models.IntegerField(default=0)
    hvs07 = models.IntegerField(default=0)
    hvs08 = models.IntegerField(default=0)
    hvs15 = models.IntegerField(default=0)
    hvs18 = models.IntegerField(default=0)
    hvs19 = models.IntegerField(default=0)
    hvs21 = models.IntegerField(default=0)
    hvs22 = models.IntegerField(default=0)
    hvs24 = models.IntegerField(default=0)
    hvs25 = models.IntegerField(default=0)
    hvs26 = models.IntegerField(default=0)
    hvs27 = models.IntegerField(default=0)
    hvs28 = models.IntegerField(default=0)
    hvs29 = models.IntegerField(default=0)
    hvs30 = models.IntegerField(default=0)
    hvs31 = models.IntegerField(default=0)
    hvs32 = models.IntegerField(default=0)
    hvs33 = models.IntegerField(default=0)
    hvs34 = models.IntegerField(default=0)
    hvs35 = models.IntegerField(default=0)
    hvs38 = models.IntegerField(default=0)
    hvs46 = models.IntegerField(default=0)
    hvs47 = models.IntegerField(default=0)
    hvs51 = models.IntegerField(default=0)
    hvs56 = models.IntegerField(default=0)
    hvs57 = models.IntegerField(default=0)
    hvs59 = models.IntegerField(default=0)
    hvventiayn = models.CharField(max_length=10, blank=True, null=True)
    hvventisoayn = models.CharField(max_length=10, blank=True, null=True)
    
    last_updated = models.DateTimeField(auto_now=True)

class HospitalSevereMessage(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='severe_messages')
    message = models.TextField(blank=True, null=True)
    message_type = models.CharField(max_length=20, blank=True, null=True)
    severe_code = models.CharField(max_length=10, blank=True, null=True)
    severe_name = models.CharField(max_length=50, blank=True, null=True)
    display_yn = models.CharField(max_length=5, blank=True, null=True)
    display_method = models.CharField(max_length=10, blank=True, null=True)
    start_time = models.CharField(max_length=20, blank=True, null=True)
    end_time = models.CharField(max_length=20, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

class UpdateLog(models.Model):
    update_key = models.CharField(max_length=20, primary_key=True)
    updated_at = models.DateTimeField(auto_now=True)

class UserLocationLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    user_email = models.EmailField(blank=True, null=True)
    sign_kind = models.IntegerField(default=1)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius = models.IntegerField(default=10) 
    location_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_email} - {self.location_text} ({self.created_at})"