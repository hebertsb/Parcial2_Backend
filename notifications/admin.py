from django.contrib import admin
from .models import DeviceToken, Notification, NotificationPreference


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'device_name', 'is_active', 'last_used', 'created_at']
    list_filter = ['platform', 'is_active', 'created_at']
    search_fields = ['user__username', 'device_name', 'token']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'status', 'sent_at', 'created_at']
    list_filter = ['notification_type', 'status', 'created_at', 'sent_at']
    search_fields = ['user__username', 'title', 'body']
    readonly_fields = ['created_at', 'updated_at', 'sent_at', 'read_at', 'fcm_message_id']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('user', 'notification_type', 'title', 'body')
        }),
        ('Estado', {
            'fields': ('status', 'sent_at', 'read_at')
        }),
        ('Firebase', {
            'fields': ('fcm_message_id', 'error_message')
        }),
        ('Datos Adicionales', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'enabled', 'sale_notifications', 'product_notifications', 
                    'report_notifications', 'ml_notifications', 'system_notifications']
    list_filter = ['enabled', 'sale_notifications', 'product_notifications']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']
