"""
Core models for the vulnerability dashboard.
"""
from django.db import models


class TimestampedModel(models.Model):
    """
    Abstract base model with timestamp fields.
    All models should inherit from this to track creation and modification times.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class ImportLog(TimestampedModel):
    """
    Track import operations for all data sources.
    """
    SOURCE_CHOICES = [
        ('CPE', 'CPE Repository'),
        ('CVE', 'CVE Repository'),
        ('LINUX', 'Linux CVE Announcements'),
    ]
    
    OPERATION_CHOICES = [
        ('FULL_IMPORT', 'Full Import'),
        ('INCREMENTAL', 'Incremental Update'),
    ]
    
    STATUS_CHOICES = [
        ('STARTED', 'Started'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial Success'),
    ]
    
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    records_processed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.source} - {self.operation} - {self.status} ({self.created_at})"