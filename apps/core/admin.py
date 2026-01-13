"""
Admin configuration for core models.
"""
from django.contrib import admin
from .models import ImportLog


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    """
    Admin interface for ImportLog model.
    """
    list_display = ['source', 'operation', 'status', 'records_processed', 'created_at']
    list_filter = ['source', 'operation', 'status', 'created_at']
    search_fields = ['source', 'operation']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']