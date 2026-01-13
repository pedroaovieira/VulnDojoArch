"""
URL configuration for CPE Repository app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for API endpoints
router = DefaultRouter()
router.register(r'cpe', views.CPERecordViewSet, basename='cpe')

app_name = 'cpe_repository'

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
]