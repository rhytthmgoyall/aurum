from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    # path('cart/', views.cart_detail, name='cart_detail'),
    # path('cart/add/', views.cart_add, name='cart_add'),
    # path('cart/update/', views.cart_update, name='cart_update'),
    # path('cart/remove/', views.cart_remove, name='cart_remove'),
    path('search/', views.search_view, name='search'),
    path("product/<int:id>/", views.product_detail, name="product_detail")
    # path('api/product/<int:product_id>/', views.product_detail_api, name='product_detail_api'),
]