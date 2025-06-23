from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from .models import InstagramClient, InstagramMessage, SystemPrompt
from .admin_views import instagram_dashboard


class InstagramMessageInline(admin.TabularInline):
    model = InstagramMessage
    extra = 0
    readonly_fields = ('sender', 'content', 'timestamp')
    fields = ('sender', 'content', 'timestamp')
    ordering = ('timestamp',)
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class InstagramClientAdmin(admin.ModelAdmin):
    list_display = ('instagram_id', 'created_at', 'message_count')
    search_fields = ('instagram_id',)
    readonly_fields = ('instagram_id', 'created_at', 'updated_at')
    inlines = [InstagramMessageInline]
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


class InstagramMessageAdmin(admin.ModelAdmin):
    list_display = ('client', 'sender', 'short_content', 'timestamp')
    list_filter = ('sender', 'timestamp')
    search_fields = ('content', 'client__instagram_id')
    readonly_fields = ('client', 'sender', 'content', 'timestamp')
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Content'


class SystemPromptAdmin(admin.ModelAdmin):
    list_display = ('short_content', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    fields = ('content', 'is_active')
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Content'
    
    def save_model(self, request, obj, form, change):
        if obj.is_active:
            # Ensure only one active prompt
            SystemPrompt.objects.filter(is_active=True).update(is_active=False)
        super().save_model(request, obj, form, change)


# Register the dashboard view with the admin site

# Register all models with the admin site
admin.site.register(InstagramClient, InstagramClientAdmin)
admin.site.register(InstagramMessage, InstagramMessageAdmin)
admin.site.register(SystemPrompt, SystemPromptAdmin)

# Create a custom URL pattern for the admin site
from django.urls import path

# Register the dashboard URL in the urls.py file
# This will be imported in the app's urls.py file
