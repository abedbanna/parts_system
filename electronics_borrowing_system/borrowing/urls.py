from django.urls import path
from . import views

app_name = 'borrowing'

urlpatterns = [
    # Main pages
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_request, name='create_request'),
    path('requests/', views.request_list, name='request_list'),
    path('request/<int:pk>/', views.request_detail, name='request_detail'),

    # Admin pages
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/approve/<int:pk>/', views.approve_request, name='approve_request'),
    path('admin/reject/<int:pk>/', views.reject_request, name='reject_request'),

    # AJAX endpoints for parts search
    path('parts/autocomplete/', views.parts_autocomplete, name='parts_autocomplete'),
    path('parts/<int:part_id>/details/', views.get_part_details, name='part_details'),

    # Debug and utility
    path('debug/requests/', views.debug_requests, name='debug_requests'),
    path('debug/clear/', views.clear_temp_storage, name='clear_temp_storage'),
]
