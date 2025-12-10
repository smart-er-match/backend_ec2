from rest_framework import serializers
from rest_framework import serializers
from .models import Hospital, Review, Comment
from accounts.serializers import UserSerializer

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
    hvec = serializers.IntegerField(allow_null=True)
    hvctayn = serializers.BooleanField(allow_null=True)

class CommentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'review', 'user', 'content', 'created_at', 'updated_at', 'is_owner']
        read_only_fields = ['id', 'review', 'user', 'created_at', 'updated_at']

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False

class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'hospital', 'user', 'content', 'rating', 'created_at', 'updated_at', 'comments', 'is_owner']
        read_only_fields = ['id', 'hospital', 'user', 'created_at', 'updated_at', 'comments']

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.user == request.user
        return False

class HospitalListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hospital
        fields = ['hpid', 'name', 'address', 'first_address', 'second_address', 'third_address', 'main_phone', 'emergency_phone', 'latitude', 'longitude']
