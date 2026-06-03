#views.py
import json

from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import Product

@ensure_csrf_cookie
def home(request):
    products = Product.objects.all()
    return render(
        request,
        "shop/products/e-commerce.html",
        {"products": products},
    )

def product_detail(request, id):
    product = get_object_or_404(Product, id=id)

    reviews = product.reviews.all().order_by("-created_at")

    return render(request, "shop/products/product_detail.html", {
        "product": product,
        "reviews": reviews,
    })

from django.core.paginator import Paginator

def search_view(request):
    query = request.GET.get('q', '')

    if query:
        results = Product.objects.filter(name__icontains=query)
    else:
        results = Product.objects.none()

    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(word in user_agent for word in ['mobile', 'android', 'iphone'])

    if is_mobile:
        return render(request, 'shop/products/search_results.html', {
            'query': query,
            'products': results,
            'is_mobile': True,
        })

    paginator = Paginator(results, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'shop/products/search_results.html', {
        'query': query,
        'products': page_obj,
        'page_obj': page_obj,
        'is_mobile': False,
    })

def product_detail_api(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    data = {
        'id': product.id,
        'name': product.name,
        'price': str(product.price),
        'description': product.description,
        'image': product.image.url if product.image else None,
    }
    return JsonResponse(data)