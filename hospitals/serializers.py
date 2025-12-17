from rest_framework import serializers
from .models import Hospital, Review, Comment, HospitalRealtimeStatus
from accounts.serializers import UserSerializer

class HospitalRealtimeStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalRealtimeStatus
        fields = ['hvec', 'hvs01', 'hvctayn', 'hvmriayn', 'last_updated']

class HospitalResponseSerializer(serializers.Serializer):
    hpid = serializers.CharField()
    name = serializers.CharField()
    address = serializers.CharField()
    phone = serializers.CharField(allow_null=True)
    er_phone = serializers.CharField(allow_null=True)
    distance = serializers.FloatField()
    score = serializers.FloatField()
    matched_reasons = serializers.ListField(child=serializers.CharField())
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    description = serializers.CharField(allow_null=True, required=False)
    hvec = serializers.IntegerField(allow_null=True)
    hvs01 = serializers.IntegerField(allow_null=True)
    hvctayn = serializers.CharField(allow_null=True) # Boolean or String (Y/N)
    severe_messages = serializers.ListField(child=serializers.DictField(), allow_empty=True)
    ai_matches = serializers.DictField(allow_empty=True)
    bookmark_count = serializers.IntegerField(default=0)
    is_bookmarked = serializers.BooleanField(default=False)
    average_rating = serializers.FloatField(default=0.0)
    review_count = serializers.IntegerField(default=0)

class CommentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'review', 'user', 'content', 'created_at', 'updated_at', 'is_owner']
        read_only_fields = ['id', 'review', 'user', 'created_at', 'updated_at']

    def get_user(self, obj):
        if obj.user.is_withdrawn:
            return {"email": "탈퇴한 회원입니다", "name": "탈퇴한 회원", "is_withdrawn": True}
        return UserSerializer(obj.user, context=self.context).data

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False

class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'hospital', 'user', 'content', 'rating', 'created_at', 'updated_at', 'comments', 'comment_count', 'is_owner']
        read_only_fields = ['id', 'hospital', 'user', 'created_at', 'updated_at', 'comments']

    def get_user(self, obj):
        if obj.user.is_withdrawn:
            return {"email": "탈퇴한 회원입니다", "name": "탈퇴한 회원", "is_withdrawn": True}
        return UserSerializer(obj.user, context=self.context).data

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False

class HospitalListSerializer(serializers.ModelSerializer):
    realtime_status = HospitalRealtimeStatusSerializer(read_only=True)
    bookmark_count = serializers.IntegerField(source='bookmarked_by.count', read_only=True)
    is_bookmarked = serializers.BooleanField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Hospital
        fields = ['hpid', 'name', 'address', 'first_address', 'second_address', 'third_address', 'main_phone', 'emergency_phone', 'latitude', 'longitude', 'description', 'realtime_status', 'bookmark_count', 'is_bookmarked', 'average_rating', 'review_count']

