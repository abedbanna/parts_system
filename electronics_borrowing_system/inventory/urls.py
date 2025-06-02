# ============================================================================
# inventory/urls.py
# ============================================================================

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Main inventory dashboard
    path('', views.inventory_dashboard, name='dashboard'),

    # Parts management
    path('add/', views.add_part, name='add_part'),
    path('parts/', views.part_list, name='part_list'),
    path('parts/<int:pk>/', views.part_detail, name='part_detail'),
    path('parts/<int:pk>/edit/', views.edit_part, name='edit_part'),
    path('parts/<int:pk>/delete/', views.delete_part, name='delete_part'),

    # Reports
    path('low-stock/', views.low_stock_report, name='low_stock_report'),

    # API endpoints
    path('api/stats/', views.inventory_stats_api, name='stats_api'),

    # Testing/Demo
    path('create-sample/', views.create_sample_inventory, name='create_sample'),
]

