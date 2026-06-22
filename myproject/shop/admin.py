from django.contrib import admin
from .models import Product,Review
from .models import ShippingAddress

admin.site.register(Product)
admin.site.register(Review)
admin.site.register(ShippingAddress)