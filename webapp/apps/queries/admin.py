from django.contrib import admin

from .models import Query


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'short_text', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('text', 'user__username')
    readonly_fields = ('created_at',)
