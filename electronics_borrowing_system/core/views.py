from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    """Main system dashboard - redirect to borrowing dashboard"""
    return redirect('borrowing:dashboard')
