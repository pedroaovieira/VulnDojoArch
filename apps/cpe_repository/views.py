"""
Django REST Framework views for CPE Repository.
"""
from django.db import models
from django.db.models import Q, Count
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.pagination import StandardResultsSetPagination
from .models import CPERecord
from .serializers import CPERecordSerializer, CPERecordListSerializer, CPESearchSerializer


class CPERecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for CPE records providing list, detail, and search functionality.
    
    Provides the following endpoints:
    - GET /api/cpe/ - List all CPE records (paginated)
    - GET /api/cpe/{id}/ - Get specific CPE record details
    - GET /api/cpe/search/ - Search CPE records with filters
    """
    
    queryset = CPERecord.objects.all()
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    
    # Filtering configuration
    filterset_fields = {
        'part': ['exact'],
        'vendor': ['exact', 'icontains'],
        'product': ['exact', 'icontains'],
        'version': ['exact', 'icontains'],
        'deprecated': ['exact'],
        'created_at': ['gte', 'lte'],
        'updated_at': ['gte', 'lte'],
    }
    
    # Search configuration
    search_fields = ['vendor', 'product', 'version', 'cpe_name']
    
    # Ordering configuration
    ordering_fields = ['vendor', 'product', 'version', 'created_at', 'updated_at']
    ordering = ['vendor', 'product', 'version']
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.
        Use detailed serializer for detail view, simplified for list.
        """
        if self.action == 'retrieve':
            return CPERecordSerializer
        return CPERecordListSerializer
    
    def get_queryset(self):
        """
        Optionally filter the queryset based on query parameters.
        """
        queryset = CPERecord.objects.all()
        
        # Add any custom filtering logic here
        # The DjangoFilterBackend handles most filtering automatically
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Advanced search endpoint with custom search logic.
        
        GET /api/cpe/search/?q=apache&part=a&deprecated=false
        """
        serializer = CPESearchSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        queryset = self.get_queryset()
        
        # Apply search filters
        search_params = serializer.validated_data
        
        # General search query
        if 'q' in search_params:
            query = search_params['q']
            queryset = queryset.filter(
                Q(vendor__icontains=query) |
                Q(product__icontains=query) |
                Q(version__icontains=query) |
                Q(cpe_name__icontains=query)
            )
        
        # Specific field filters
        if 'vendor' in search_params:
            queryset = queryset.filter(vendor__icontains=search_params['vendor'])
        
        if 'product' in search_params:
            queryset = queryset.filter(product__icontains=search_params['product'])
        
        if 'version' in search_params:
            queryset = queryset.filter(version__icontains=search_params['version'])
        
        if 'part' in search_params:
            queryset = queryset.filter(part=search_params['part'])
        
        if 'deprecated' in search_params:
            queryset = queryset.filter(deprecated=search_params['deprecated'])
        
        # Apply ordering
        ordering = search_params.get('ordering', 'vendor')
        queryset = queryset.order_by(ordering)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CPERecordListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = CPERecordListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get statistics about CPE records.
        
        GET /api/cpe/stats/
        """
        queryset = self.get_queryset()
        
        stats = {
            'total_records': queryset.count(),
            'by_part': {
                'applications': queryset.filter(part='a').count(),
                'operating_systems': queryset.filter(part='o').count(),
                'hardware': queryset.filter(part='h').count(),
            },
            'deprecated_count': queryset.filter(deprecated=True).count(),
            'active_count': queryset.filter(deprecated=False).count(),
            'top_vendors': list(
                queryset.values('vendor')
                .annotate(count=Count('vendor'))
                .order_by('-count')[:10]
                .values_list('vendor', 'count')
            ),
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def vendors(self, request):
        """
        Get list of unique vendors.
        
        GET /api/cpe/vendors/
        """
        vendors = (
            self.get_queryset()
            .values_list('vendor', flat=True)
            .distinct()
            .order_by('vendor')
        )
        
        # Apply search filter if provided
        search = request.query_params.get('search')
        if search:
            vendors = vendors.filter(vendor__icontains=search)
        
        # Limit results to prevent huge responses
        vendors = vendors[:100]
        
        return Response({'vendors': list(vendors)})
    
    @action(detail=False, methods=['get'])
    def products(self, request):
        """
        Get list of products for a specific vendor.
        
        GET /api/cpe/products/?vendor=apache
        """
        vendor = request.query_params.get('vendor')
        if not vendor:
            return Response(
                {'error': 'vendor parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        products = (
            self.get_queryset()
            .filter(vendor__iexact=vendor)
            .values_list('product', flat=True)
            .distinct()
            .order_by('product')
        )
        
        # Apply search filter if provided
        search = request.query_params.get('search')
        if search:
            products = products.filter(product__icontains=search)
        
        # Limit results
        products = products[:100]
        
        return Response({
            'vendor': vendor,
            'products': list(products)
        })
    
    @action(detail=False, methods=['get'])
    def versions(self, request):
        """
        Get list of versions for a specific vendor/product combination.
        
        GET /api/cpe/versions/?vendor=apache&product=http_server
        """
        vendor = request.query_params.get('vendor')
        product = request.query_params.get('product')
        
        if not vendor or not product:
            return Response(
                {'error': 'Both vendor and product parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        versions = (
            self.get_queryset()
            .filter(vendor__iexact=vendor, product__iexact=product)
            .exclude(version='')  # Exclude empty versions
            .values_list('version', flat=True)
            .distinct()
            .order_by('version')
        )
        
        # Limit results
        versions = versions[:100]
        
        return Response({
            'vendor': vendor,
            'product': product,
            'versions': list(versions)
        })