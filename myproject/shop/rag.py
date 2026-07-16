from django.conf import settings
from django.utils import timezone
from groq import Groq
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer


_groq_client = None
_qdrant = None
_embedding_model = None


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


def get_qdrant_client():
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=settings.QDRANT_URL, timeout=60.0)
    return _qdrant


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.RAG_EMBEDDING_MODEL)
    return _embedding_model


def is_greeting(message):
    normalized = message.strip().lower()
    return normalized in {
        "hi",
        "hello",
        "hey",
        "namaste",
        "namaskar",
        "bonjour",
        "good morning",
        "good afternoon",
        "good evening",
    }


def is_thanks(message):
    normalized = message.strip().lower()
    return normalized in {"thanks", "thank you", "thx", "ty", "thankyou"}


def retrieve_support_chunks(question, limit=6):
    embedding = get_embedding_model().encode(
        question,
        normalize_embeddings=True,
    ).tolist()

    response = get_qdrant_client().query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=embedding,
        limit=limit,
        score_threshold=0.22,
    )

    return [
        {
            "title": item.payload.get("title", ""),
            "source": item.payload.get("source", ""),
            "source_type": item.payload.get("source_type", ""),
            "source_id": item.payload.get("source_id", ""),
            "url": item.payload.get("url", ""),
            "content": item.payload.get("content", ""),
            "price": item.payload.get("price", ""),
            "stock": item.payload.get("stock", ""),
            "category": item.payload.get("category", ""),
            "score": item.score,
        }
        for item in response.points
    ]


def build_retrieved_context(chunks):
    if not chunks:
        return "RETRIEVED AURUM KNOWLEDGE: None found."

    lines = ["RETRIEVED AURUM KNOWLEDGE:"]

    for index, chunk in enumerate(chunks, start=1):
        lines.append(
            f"\n{index}. {chunk['title']}"
            f"\n   Type: {chunk['source_type']}"
            f"\n   Source: {chunk['source']}"
            f"\n   URL: {chunk['url']}"
            f"\n   Price: {chunk['price']}"
            f"\n   Stock: {chunk['stock']}"
            f"\n   Category: {chunk['category']}"
            f"\n   Content: {chunk['content']}"
        )

    return "\n".join(lines)


def build_user_context(user):
    if not user or not user.is_authenticated:
        return "CURRENT CUSTOMER: Guest visitor. No account, cart, order, refund, or address data is available."

    from shop.models import Cart, Order, Payment, ShippingAddress

    lines = [
        f"CURRENT CUSTOMER: {user.username}",
        f"Email: {user.email or 'Not provided'}",
    ]

    addresses = ShippingAddress.objects.filter(user=user).order_by("-created_at")[:3]
    if addresses:
        lines.append("\nSAVED ADDRESSES:")
        for address in addresses:
            lines.append(
                f"- {address.full_name}, {address.phone}, {address.address_line}, "
                f"{address.city}, {address.state}, {address.postal_code}, {address.country}"
            )
    else:
        lines.append("\nSAVED ADDRESSES: None found.")

    cart = Cart.objects.filter(user=user).prefetch_related("items__product").first()
    if cart and cart.items.exists():
        lines.append("\nCURRENT CART:")
        cart_total = 0
        for item in cart.items.all():
            subtotal = item.product.price * item.quantity
            cart_total += subtotal
            lines.append(
                f"- {item.product.name} x {item.quantity}, "
                f"Price INR {item.product.price}, Subtotal INR {subtotal}, Stock {item.product.stock}"
            )
        lines.append(f"Cart subtotal: INR {cart_total}")
    else:
        lines.append("\nCURRENT CART: Empty.")

    orders = (
        Order.objects
        .filter(user=user)
        .prefetch_related("items")
        .select_related("shipping_address")
        .order_by("-created_at")[:3]
    )

    if orders:
        lines.append("\nRECENT ORDERS:")
        for order in orders:
            order_date = timezone.localtime(order.created_at).strftime("%d %b %Y, %I:%M %p")
            items = []
            for item in order.items.all():
                items.append(
                    f"{item.product_name} x {item.quantity}, "
                    f"Item total INR {item.item_total}"
                )

            lines.append(
                f"- Order #{order.id}, Date: {order_date}, Status: {order.status}, "
                f"Subtotal INR {order.subtotal}, Shipping INR {order.shipping}, "
                f"Tax INR {order.tax}, Total INR {order.total}, Items: [{'; '.join(items)}]"
            )
    else:
        lines.append("\nRECENT ORDERS: None found.")

    payments = (
        Payment.objects
        .filter(user=user)
        .select_related("order")
        .prefetch_related("refunds")
        .order_by("-created_at")[:3]
    )

    if payments:
        lines.append("\nRECENT PAYMENTS AND REFUNDS:")
        for payment in payments:
            lines.append(
                f"- Payment for Order #{payment.order_id or 'N/A'}, "
                f"Status: {payment.status}, Amount: {payment.amount} {payment.currency}, "
                f"Refunded amount: {payment.refunded_amount}"
            )

            for refund in payment.refunds.all():
                lines.append(
                    f"  Refund {refund.razorpay_refund_id}: "
                    f"Status {refund.status}, Amount {refund.amount}, Reason: {refund.reason or 'Not provided'}"
                )
    else:
        lines.append("\nRECENT PAYMENTS AND REFUNDS: None found.")

    return "\n".join(lines)


def build_chat_history_context(conversation):
    if not conversation:
        return "RECENT CHAT HISTORY: None."

    messages = list(conversation.messages.order_by("-created_at")[1:9])
    messages.reverse()

    if not messages:
        return "RECENT CHAT HISTORY: None."

    lines = ["RECENT CHAT HISTORY:"]
    for message in messages:
        if message.is_ai_message:
            speaker = "AURUM Assistant"
        elif message.is_staff_message:
            speaker = "Support"
        else:
            speaker = "Customer"

        lines.append(f"{speaker}: {message.body}")

    return "\n".join(lines)


def generate_support_reply(question, user=None, conversation=None):
    if not settings.GROQ_API_KEY:
        return "AI support is not configured yet. A support specialist will help you shortly."

    if is_greeting(question):
        return "Namaste, welcome to AURUM Support. How can I help you today?"

    if is_thanks(question):
        return "You are very welcome. I am here if you need help with products, shipping, returns, refunds, sizing, product care, cart, or orders."

    try:
        chunks = retrieve_support_chunks(question)
    except Exception:
        chunks = []

    retrieved_context = build_retrieved_context(chunks)
    user_context = build_user_context(user)
    chat_history_context = build_chat_history_context(conversation)

    try:
        response = get_groq_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AURUM Support, a warm luxury ecommerce support assistant.\n"
                        "You help customers with AURUM products, recommendations, cart, orders, payments, refunds, saved addresses, shipping, returns, sizing, materials, and product care.\n"
                        "Use RETRIEVED AURUM KNOWLEDGE for product and policy facts.\n"
                        "Use CURRENT CUSTOMER CONTEXT only for the currently authenticated customer.\n"
                        "Never reveal another customer's private data.\n"
                        "Never invent products, prices, stock, orders, payments, refunds, policies, or timelines.\n"
                        "If the user asks about cart/orders/refunds/addresses and the context has the answer, answer directly.\n"
                        "If relevant products are retrieved, recommend only those products and explain briefly why they match.\n"
                        "If you do not have enough information, ask one helpful follow-up question or say a support specialist can help.\n"
                        "Keep replies concise, polished, and friendly.\n"
                        "Use plain text. Do not use markdown headings."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{retrieved_context}\n\n"
                        f"{user_context}\n\n"
                        f"{chat_history_context}\n\n"
                        f"CUSTOMER MESSAGE: {question}"
                    ),
                },
            ],
            temperature=0.35,
            max_completion_tokens=420,
        )
    except Exception:
        return "I can help with AURUM products, shipping, returns, refunds, sizing, product care, cart, and orders. What would you like to know?"

    return response.choices[0].message.content.strip()