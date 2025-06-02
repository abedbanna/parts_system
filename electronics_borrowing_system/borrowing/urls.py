# borrowing/urls.py

from django.urls import path
from . import views

app_name = 'borrowing'

urlpatterns = [
    # Student views
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_request, name='create_request'),
    path('requests/', views.request_list, name='request_list'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),

    # Admin views
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/approve/<int:pk>/', views.approve_request, name='approve_request'),
    path('admin/reject/<int:pk>/', views.reject_request, name='reject_request'),

    # Debug views
    path('debug/requests/', views.debug_requests, name='debug_requests'),
    path('debug/clear/', views.clear_temp_storage, name='clear_temp_storage'),
]
