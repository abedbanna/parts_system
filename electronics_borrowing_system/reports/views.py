from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def analytics_dashboard(request):
    """Main analytics dashboard"""
    context = {
        'total_parts': 0,
        'active_borrows': 0,
        'pending_requests': 0,
        'overdue_requests': 0,
    }
    return render(request, 'reports/analytics.html', context)

@staff_member_required
def borrowing_stats(request):
    """Borrowing statistics"""
    context = {'stats': {}}
    return render(request, 'reports/borrowing_stats.html', context)

@staff_member_required
def parts_usage(request):
    """Parts usage statistics"""
    context = {'usage_stats': []}
    return render(request, 'reports/parts_usage.html', context)

@staff_member_required
def user_activity(request):
    """User activity reports"""
    context = {'activity_data': []}
    return render(request, 'reports/user_activity.html', context)
