from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.part_list, name='part_list'),
    path('part/<int:pk>/', views.part_detail, name='part_detail'),
    path('categories/', views.category_list, name='category_list'),
    path('search/', views.search_parts, name='search_parts'),
]
