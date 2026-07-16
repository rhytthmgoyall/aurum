from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    path("search/", views.search_view, name="search"),
    path("shop/<slug:category_slug>/", views.category_browse, name="category_browse"),
    path("shop/<slug:category_slug>/<slug:subcategory_slug>/", views.category_browse, name="subcategory_browse"),
    path("product/<int:id>/", views.product_detail, name="product_detail"),
    path("products/<int:id>/variant-stock/", views.product_variant_stock_api, name="product_variant_stock_api"),

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
    path("order/confirmation/<int:order_id>/", views.order_confirmation, name="order_confirmation"),
    path("orders/", views.order_history, name="order_history"),
    path("orders/<int:order_id>/refund/request/", views.refund_request, name="refund_request"),
    path("refunds/<int:refund_request_id>/", views.refund_status, name="refund_status"),
    path("orders/<int:order_id>/refund/", views.request_order_refund, name="request_order_refund"),
    path("orders/<int:order_id>/items/<int:item_id>/refund/", views.request_order_item_refund, name="request_order_item_refund"),
    path("api/cart/update/<int:product_id>/", views.update_cart_item_api, name="update_cart_item_api"),
    path("api/cart/merge/", views.merge_cart_api, name="merge_cart_api"),
    path("api/cart/remove/<int:product_id>/", views.remove_from_cart_api, name="remove_from_cart_api"),
    path("profile/", views.profile_page, name="profile"),
    path("profile/wallet/", views.wallet_balance, name="wallet_balance"),
    path("profile/wallet/top-up/", views.wallet_topup, name="wallet_topup"),
    path("profile/wallet/top-up/verify/", views.wallet_topup_verify, name="wallet_topup_verify"),
    path("profile/membership/", views.membership, name="membership"),
    path("profile/membership/subscribe/", views.membership_subscribe, name="membership_subscribe"),
    path("profile/membership/verify/", views.membership_verify, name="membership_verify"),
    path("profile/membership/cancel/", views.membership_cancel, name="membership_cancel"),
    path("api/profile/", views.profile_api, name="profile_api"),
    path("api/shipping-address/", views.save_shipping_address_api, name="save_shipping_address_api"),
    path("api/recommendations/", views.recommendations_api, name="recommendations_api"),
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
    path("api/payment/create/", views.create_razorpay_order, name="create_razorpay_order"),
    path("api/order/confirm/", views.create_order, name="create_order"),
    path("admin/refund-payment/<int:payment_id>/", views.refund_payment, name="refund_payment"),
    path("api/support/agora-token/", views.agora_support_token, name="agora_support_token"),
    path("api/support/history/", views.support_chat_history, name="support_chat_history"),
    path("api/support/message/", views.save_support_chat_message, name="save_support_chat_message"),
    path("api/support/ai-reply/", views.support_ai_reply, name="support_ai_reply"),
    path("support/chat/", views.support_chat_dashboard, name="support_chat_dashboard"),
    path("api/support/guest-start/", views.start_guest_support_chat, name="start_guest_support_chat"),
    path("webhooks/razorpay/", views.razorpay_webhook_view, name="razorpay_webhook"),
]
