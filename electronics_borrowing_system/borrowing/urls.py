# ============================================================================
# FILE: borrowing/urls.py
# ============================================================================

from django.urls import path
from . import views

app_name = 'borrowing'

urlpatterns = [
    # Main URLs
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Request Management
    path('create/', views.create_request, name='create_request'),
    path('requests/', views.request_list, name='request_list'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),

    # Admin URLs
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/approve/<int:pk>/', views.approve_request, name='approve_request'),
    path('admin/reject/<int:pk>/', views.reject_request, name='reject_request'),

    # Debug/Testing URLs (remove in production)
    path('debug/requests/', views.debug_requests, name='debug_requests'),
    path('debug/clear/', views.clear_temp_storage, name='clear_temp_storage'),
]
