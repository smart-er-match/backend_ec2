from rest_framework import serializers
from .models import Hospital

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
