from django.contrib import admin
from .models import Hospital, HospitalRealtimeStatus, HospitalSevereMessage, UserLocationLog, Category, SymptomSearchLog

@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ('hpid', 'name', 'address', 'main_phone', 'latitude', 'longitude')
    search_fields = ('name', 'hpid', 'address')

@admin.register(HospitalRealtimeStatus)
class HospitalRealtimeStatusAdmin(admin.ModelAdmin):
    list_display = ('hospital', 'last_updated', 'hvec', 'hvoc')
    raw_id_fields = ('hospital',)

@admin.register(HospitalSevereMessage)
class HospitalSevereMessageAdmin(admin.ModelAdmin):
    list_display = ('hospital', 'message_type', 'severe_name', 'start_time', 'created_at')
    list_filter = ('message_type', 'severe_name', 'created_at')
    raw_id_fields = ('hospital',)

@admin.register(UserLocationLog)
class UserLocationLogAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'location_text', 'created_at')
    list_filter = ('created_at',)

@admin.register(SymptomSearchLog)
class SymptomSearchLogAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'symptoms', 'latitude', 'longitude', 'radius', 'created_at')
    list_filter = ('created_at',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)