from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from .models import Property
from .serializers import PropertySerializer, PropertyListSerializer
from .constants import IRAQ_GOVERNORATES


class PropertyViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for viewing properties with governorate filtering"""
    
    queryset = Property.objects.select_related('broker', 'owner').prefetch_related('images').filter(
        Q(status='ready') | Q(status='sale') | Q(status='rent') | Q(status='investment')
    )
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'status', 'district', 'bedrooms', 'bathrooms', 'is_featured', 'is_promoted']
    search_fields = ['title', 'description', 'location', 'district']
    ordering_fields = ['price', 'area', 'created_at', 'views_count']
    ordering = ['-is_featured', '-is_promoted', '-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PropertyListSerializer
        return PropertySerializer
    
    @action(detail=False, methods=['get'])
    def by_governorate(self, request):
        """Get properties by governorate"""
        governorate = request.query_params.get('governorate')
        
        if not governorate:
            return Response({
                'error': 'governorate parameter is required',
                'available_governorates': [code for code, _ in IRAQ_GOVERNORATES]
            }, status=400)
        
        # Validate governorate
        valid_governorates = [code for code, _ in IRAQ_GOVERNORATES]
        if governorate not in valid_governorates:
            return Response({
                'error': f'Invalid governorate. Valid options: {valid_governorates}'
            }, status=400)
        
        # Filter by governorate (using district field which contains location info)
        # Since the model uses district for Nasiriyah-specific locations,
        # we'll filter by location containing the governorate name
        governorate_name = dict(IRAQ_GOVERNORATES).get(governorate, governorate)
        
        properties = self.get_queryset().filter(
            Q(location__icontains=governorate_name) |
            Q(district__icontains=governorate_name)
        )
        
        # Apply additional filters
        property_type = request.query_params.get('type')
        status = request.query_params.get('status')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        min_area = request.query_params.get('min_area')
        max_area = request.query_params.get('max_area')
        
        if property_type:
            properties = properties.filter(type=property_type)
        if status:
            properties = properties.filter(status=status)
        if min_price:
            properties = properties.filter(price__gte=min_price)
        if max_price:
            properties = properties.filter(price__lte=max_price)
        if min_area:
            properties = properties.filter(area__gte=min_area)
        if max_area:
            properties = properties.filter(area__lte=max_area)
        
        # Pagination
        page = self.paginate_queryset(properties)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(properties, many=True)
        return Response({
            'governorate': governorate,
            'governorate_name': governorate_name,
            'count': properties.count(),
            'properties': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def governorates(self, request):
        """Get list of available governorates"""
        return Response({
            'governorates': [
                {'code': code, 'name': name}
                for code, name in IRAQ_GOVERNORATES
            ]
        })
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured properties"""
        properties = self.get_queryset().filter(is_featured=True)
        
        governorate = request.query_params.get('governorate')
        if governorate:
            governorate_name = dict(IRAQ_GOVERNORATES).get(governorate, governorate)
            properties = properties.filter(
                Q(location__icontains=governorate_name) |
                Q(district__icontains=governorate_name)
            )
        
        page = self.paginate_queryset(properties)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(properties, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def promoted(self, request):
        """Get promoted properties"""
        properties = self.get_queryset().filter(is_promoted=True)
        
        governorate = request.query_params.get('governorate')
        if governorate:
            governorate_name = dict(IRAQ_GOVERNORATES).get(governorate, governorate)
            properties = properties.filter(
                Q(location__icontains=governorate_name) |
                Q(district__icontains=governorate_name)
            )
        
        page = self.paginate_queryset(properties)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(properties, many=True)
        return Response(serializer.data)
