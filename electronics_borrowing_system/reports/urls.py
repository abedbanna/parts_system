from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.analytics_dashboard, name='dashboard'),
    path('borrowing-stats/', views.borrowing_stats, name='borrowing_stats'),
    path('parts-usage/', views.parts_usage, name='parts_usage'),
    path('user-activity/', views.user_activity, name='user_activity'),
]
