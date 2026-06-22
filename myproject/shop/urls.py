from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    path("search/", views.search_view, name="search"),
    path("product/<int:id>/", views.product_detail, name="product_detail"),

    path("signup/", views.signup_page, name="signup"),
    path("forgot-password/", views.forgot_password_page, name="forgot_password"),
    
    path("logout/", views.logout_view, name="logout"),
    path("login/", views.login_view, name="login"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("api/signup/", views.signup_start_api, name="signup_start_api"),
    path("api/signup/verify/", views.signup_verify_api, name="signup_verify_api"),
    path("api/signup/resend/", views.signup_resend_api, name="signup_resend_api"),
    path("api/password-reset/", views.password_reset_start_api, name="password_reset_start_api"),
    path("api/password-reset/verify/", views.password_reset_verify_api, name="password_reset_verify_api"),
    path("api/password-reset/complete/", views.password_reset_complete_api, name="password_reset_complete_api"),
    path("checkout/", views.checkout_page, name="checkout"),

path(
    "api/checkout/summary/",
    views.checkout_summary_api,
    name="checkout_summary_api"
),

path(
    "api/checkout/shipping/",
    views.save_shipping_address_json,
    name="save_shipping_address_json"
),

    path("api/cart/update/<int:product_id>/", views.update_cart_item_api, name="update_cart_item_api"),
    path("api/cart/merge/", views.merge_cart_api, name="merge_cart_api"),
    path("api/cart/remove/<int:product_id>/", views.remove_from_cart_api, name="remove_from_cart_api"),
    path("profile/", views.profile_page, name="profile"),
    path("api/profile/", views.profile_api, name="profile_api"),
    path("api/shipping-address/", views.save_shipping_address_api, name="save_shipping_address_api"),
    path("cart/session/count/", views.session_cart_count, name="session_cart_count"),
    
    path(
        "auth/social-complete/",
        views.social_complete_page,
        name="social_complete",
    ),

    path("cart/", views.cart_page, name="cart"),

    path(
    "cart/session/add/<int:product_id>/",
    views.add_to_session_cart,
    name="add_to_session_cart"
    ),

    path(
    "cart/session/decrease/<int:product_id>/",
    views.decrease_session_cart,
    name="decrease_session_cart"
    ),

    path(
    "cart/session/remove/<int:product_id>/",
    views.remove_from_session_cart,
    name="remove_from_session_cart"
    ),
    path("accounts/google/login/", views.google_login, name="google_login"),
    path("accounts/google/callback/", views.google_callback, name="google_callback"),
]
