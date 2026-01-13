"""
CPE Repository models for storing Common Platform Enumeration data.
"""
from django.db import models
from apps.core.models import TimestampedModel


class CPERecord(TimestampedModel):
    """
    CPE Dictionary entry representing a Common Platform Enumeration record.
    
    Based on the NVD CPE Dictionary format, this model stores normalized
    CPE data with proper indexing for performance.
    """
    # Core CPE identification fields
    cpe_name = models.CharField(
        max_length=500, 
        unique=True, 
        db_index=True,
        help_text="Full CPE name (e.g., cpe:2.3:a:vendor:product:version:*:*:*:*:*:*:*)"
    )
    cpe_name_id = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Unique identifier for this CPE record"
    )
    
    # CPE component fields following CPE 2.3 specification
    part = models.CharField(
        max_length=1,
        help_text="CPE part: 'a' (application), 'o' (operating system), 'h' (hardware)"
    )
    vendor = models.CharField(
        max_length=200, 
        db_index=True,
        help_text="Vendor name"
    )
    product = models.CharField(
        max_length=200, 
        db_index=True,
        help_text="Product name"
    )
    version = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Product version"
    )
    update = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Product update"
    )
    edition = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Product edition"
    )
    language = models.CharField(
        max_length=10, 
        blank=True,
        help_text="Language code"
    )
    sw_edition = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Software edition"
    )
    target_sw = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Target software"
    )
    target_hw = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Target hardware"
    )
    other = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Other attributes"
    )
    
    # Deprecation tracking
    deprecated = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this CPE is deprecated"
    )
    deprecated_by = models.JSONField(
        blank=True, 
        null=True,
        help_text="List of CPE names that deprecate this one"
    )
    
    class Meta:
        verbose_name = "CPE Record"
        verbose_name_plural = "CPE Records"
        ordering = ['vendor', 'product', 'version']
        indexes = [
            models.Index(fields=['vendor', 'product']),
            models.Index(fields=['part', 'vendor']),
            models.Index(fields=['deprecated']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.vendor} {self.product} {self.version or '*'}"
    
    def get_cpe_components(self):
        """
        Return CPE components as a dictionary for easy access.
        """
        return {
            'part': self.part,
            'vendor': self.vendor,
            'product': self.product,
            'version': self.version,
            'update': self.update,
            'edition': self.edition,
            'language': self.language,
            'sw_edition': self.sw_edition,
            'target_sw': self.target_sw,
            'target_hw': self.target_hw,
            'other': self.other,
        }
    
    @property
    def is_application(self):
        """Check if this CPE represents an application."""
        return self.part == 'a'
    
    @property
    def is_operating_system(self):
        """Check if this CPE represents an operating system."""
        return self.part == 'o'
    
    @property
    def is_hardware(self):
        """Check if this CPE represents hardware."""
        return self.part == 'h'