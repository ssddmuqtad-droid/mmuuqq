from django.contrib import admin
from .models import Property

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'location', 'created_at')
    list_filter = ('created_at', 'location')
    search_fields = ('title', 'location')
    readonly_fields = ('created_at', 'updated_at')
