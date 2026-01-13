"""
Custom pagination classes and filtering utilities for the vulnerability dashboard.
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django_filters import rest_framework as filters
from django.db import models


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class with configurable page size.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000
    
    def get_paginated_response(self, data):
        """
        Return a paginated style Response object with additional metadata.
        """
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'results': data
        })


class LargeResultsSetPagination(PageNumberPagination):
    """
    Pagination class for large datasets with higher default page size.
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 10000
    
    def get_paginated_response(self, data):
        """
        Return a paginated style Response object with additional metadata.
        """
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'results': data
        })


class BaseFilterSet(filters.FilterSet):
    """
    Base filter set with common filtering functionality.
    """
    # Date range filtering
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    updated_after = filters.DateTimeFilter(field_name='updated_at', lookup_expr='gte')
    updated_before = filters.DateTimeFilter(field_name='updated_at', lookup_expr='lte')
    
    # Text search filtering
    search = filters.CharFilter(method='filter_search')
    
    def filter_search(self, queryset, name, value):
        """
        Generic search filter that can be overridden by subclasses.
        Default implementation searches across common text fields.
        """
        if not value:
            return queryset
        
        # Get all text fields from the model
        text_fields = []
        for field in self.Meta.model._meta.get_fields():
            if isinstance(field, (models.CharField, models.TextField)):
                text_fields.append(f"{field.name}__icontains")
        
        # Build Q object for OR search across text fields
        if text_fields:
            from django.db.models import Q
            q_objects = Q()
            for field in text_fields:
                q_objects |= Q(**{field: value})
            return queryset.filter(q_objects)
        
        return queryset


class SeverityFilterMixin:
    """
    Mixin for filtering by severity levels (for CVE data).
    """
    severity = filters.ChoiceFilter(
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical'),
        ],
        field_name='cvss_scores__base_severity',
        lookup_expr='iexact'
    )
    
    severity_min = filters.NumberFilter(
        field_name='cvss_scores__base_score',
        lookup_expr='gte'
    )
    
    severity_max = filters.NumberFilter(
        field_name='cvss_scores__base_score',
        lookup_expr='lte'
    )


class DateRangeFilterMixin:
    """
    Mixin for common date range filtering.
    """
    date_from = filters.DateFilter(field_name='published', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='published', lookup_expr='lte')
    
    # Year filtering
    year = filters.NumberFilter(field_name='published__year')
    month = filters.NumberFilter(field_name='published__month')


def get_filter_choices_from_model(model, field_name, limit=100):
    """
    Utility function to get distinct choices from a model field for filtering.
    
    Args:
        model: Django model class
        field_name: Name of the field to get choices from
        limit: Maximum number of choices to return
        
    Returns:
        List of tuples (value, display_name) for use in ChoiceFilter
    """
    values = (model.objects
              .values_list(field_name, flat=True)
              .distinct()
              .order_by(field_name)[:limit])
    
    return [(value, value) for value in values if value]


def apply_text_search(queryset, search_term, search_fields):
    """
    Apply text search across multiple fields using OR logic.
    
    Args:
        queryset: Django QuerySet to filter
        search_term: Text to search for
        search_fields: List of field names to search in
        
    Returns:
        Filtered QuerySet
    """
    if not search_term or not search_fields:
        return queryset
    
    from django.db.models import Q
    
    q_objects = Q()
    for field in search_fields:
        q_objects |= Q(**{f"{field}__icontains": search_term})
    
    return queryset.filter(q_objects)


def apply_date_range_filter(queryset, date_field, start_date=None, end_date=None):
    """
    Apply date range filtering to a queryset.
    
    Args:
        queryset: Django QuerySet to filter
        date_field: Name of the date field to filter on
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        
    Returns:
        Filtered QuerySet
    """
    if start_date:
        queryset = queryset.filter(**{f"{date_field}__gte": start_date})
    
    if end_date:
        queryset = queryset.filter(**{f"{date_field}__lte": end_date})
    
    return queryset