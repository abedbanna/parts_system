from django.shortcuts import render

def part_list(request):
    context = {'parts': [], 'categories': []}
    return render(request, 'inventory/part_list.html', context)

def part_detail(request, pk):
    context = {'part_id': pk, 'can_borrow': request.user.is_authenticated}
    return render(request, 'inventory/part_detail.html', context)

def category_list(request):
    context = {'categories': []}
    return render(request, 'inventory/category_list.html', context)

def search_parts(request):
    query = request.GET.get('q', '')
    context = {'query': query, 'parts': []}
    return render(request, 'inventory/search_results.html', context)
