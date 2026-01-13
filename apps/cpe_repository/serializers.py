"""
Django REST Framework serializers for CPE Repository.
"""
from rest_framework import serializers
from .models import CPERecord


class CPERecordSerializer(serializers.ModelSerializer):
    """
    Serializer for CPE records with all fields.
    """
    
    # Add computed fields
    cpe_type = serializers.SerializerMethodField()
    cpe_components = serializers.SerializerMethodField()
    
    class Meta:
        model = CPERecord
        fields = [
            'id',
            'cpe_name',
            'cpe_name_id',
            'part',
            'vendor',
            'product',
            'version',
            'update',
            'edition',
            'language',
            'sw_edition',
            'target_sw',
            'target_hw',
            'other',
            'deprecated',
            'deprecated_by',
            'cpe_type',
            'cpe_components',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'cpe_type', 'cpe_components']
    
    def get_cpe_type(self, obj):
        """Get human-readable CPE type."""
        type_mapping = {
            'a': 'Application',
            'o': 'Operating System',
            'h': 'Hardware'
        }
        return type_mapping.get(obj.part, 'Unknown')
    
    def get_cpe_components(self, obj):
        """Get CPE components as a structured object."""
        return obj.get_cpe_components()


class CPERecordListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for CPE record lists (fewer fields for performance).
    """
    
    cpe_type = serializers.SerializerMethodField()
    
    class Meta:
        model = CPERecord
        fields = [
            'id',
            'cpe_name',
            'cpe_name_id',
            'part',
            'vendor',
            'product',
            'version',
            'deprecated',
            'cpe_type',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'cpe_type']
    
    def get_cpe_type(self, obj):
        """Get human-readable CPE type."""
        type_mapping = {
            'a': 'Application',
            'o': 'Operating System',
            'h': 'Hardware'
        }
        return type_mapping.get(obj.part, 'Unknown')


class CPESearchSerializer(serializers.Serializer):
    """
    Serializer for CPE search parameters.
    """
    
    q = serializers.CharField(
        required=False,
        help_text="General search query (searches vendor, product, version)"
    )
    vendor = serializers.CharField(
        required=False,
        help_text="Filter by vendor name"
    )
    product = serializers.CharField(
        required=False,
        help_text="Filter by product name"
    )
    version = serializers.CharField(
        required=False,
        help_text="Filter by version"
    )
    part = serializers.ChoiceField(
        choices=[('a', 'Application'), ('o', 'Operating System'), ('h', 'Hardware')],
        required=False,
        help_text="Filter by CPE part type"
    )
    deprecated = serializers.BooleanField(
        required=False,
        help_text="Filter by deprecation status"
    )
    ordering = serializers.ChoiceField(
        choices=[
            'vendor', '-vendor',
            'product', '-product',
            'version', '-version',
            'created_at', '-created_at',
            'updated_at', '-updated_at'
        ],
        required=False,
        default='vendor',
        help_text="Field to order results by"
    )