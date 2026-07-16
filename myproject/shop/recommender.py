from pathlib import Path

from django.conf import settings
from django.db.models import Count, F
from django.db.models.functions import Abs

from .models import Product, ProductEmbedding, ProductInteraction


ARTIFACT_DIR = Path(settings.BASE_DIR) / "recommender_artifacts"
FAISS_INDEX_PATH = ARTIFACT_DIR / "products.faiss"
PRODUCT_IDS_PATH = ARTIFACT_DIR / "product_ids.npy"
PRODUCT_EMBEDDINGS_PATH = ARTIFACT_DIR / "product_embeddings.npy"


def ensure_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def record_product_interaction(request, product, event_type, weight=None):
    session_key = ensure_session_key(request)
    user = request.user if request.user.is_authenticated else None

    return ProductInteraction.objects.create(
        user=user,
        session_key=session_key,
        product=product,
        event_type=event_type,
        weight=weight if weight is not None else ProductInteraction.EVENT_WEIGHTS.get(event_type, 1.0),
    )


def explain_recommendations(anchor_product, products, source):
    if not products:
        return ""

    if anchor_product and source in {"faiss", "numpy"}:
        category = anchor_product.primary_category.name if anchor_product.primary_category else "collection"
        return (
            f"Selected from nearby model embeddings for this {category.lower()} piece, "
            "then filtered to avoid repeating the current product."
        )

    if source in {"category_price", "popular"}:
        return "Selected from similar category, price, and recent activity signals."

    return "Selected from your recent browsing and product similarity signals."


def fallback_product_recommendations(anchor_product=None, limit=4, exclude_ids=None):
    exclude_ids = set(exclude_ids or [])
    products = Product.objects.exclude(id__in=exclude_ids)

    if anchor_product and anchor_product.primary_category_id:
        products = (
            products.filter(categories=anchor_product.primary_category)
            .annotate(price_delta=Abs(F("price") - anchor_product.price))
            .order_by("price_delta", "id")
        )
        source = "category_price"
    else:
        products = (
            products.annotate(interaction_count=Count("interactions"))
            .order_by("-interaction_count", "id")
        )
        source = "popular"

    return list(products[:limit]), source


def _load_numpy_artifacts():
    try:
        import numpy as np
    except ImportError:
        return None, None

    if not PRODUCT_IDS_PATH.exists() or not PRODUCT_EMBEDDINGS_PATH.exists():
        return None, None

    return np.load(PRODUCT_IDS_PATH), np.load(PRODUCT_EMBEDDINGS_PATH)


def _load_anchor_vector(anchor_product):
    if not anchor_product:
        return None

    embedding = ProductEmbedding.objects.filter(product=anchor_product).first()
    if not embedding or not embedding.vector:
        return None

    try:
        import numpy as np
    except ImportError:
        return None

    vector = np.array(embedding.vector, dtype="float32")
    norm = np.linalg.norm(vector)
    if norm:
        vector = vector / norm
    return vector.reshape(1, -1)


def _retrieve_with_faiss(query_vector, limit, exclude_ids):
    try:
        import faiss
    except ImportError:
        return []

    product_ids, _ = _load_numpy_artifacts()
    if product_ids is None or not FAISS_INDEX_PATH.exists():
        return []

    index = faiss.read_index(str(FAISS_INDEX_PATH))
    distances, positions = index.search(query_vector, min(limit + len(exclude_ids) + 10, len(product_ids)))

    ids = []
    for position in positions[0]:
        if position < 0:
            continue
        product_id = int(product_ids[position])
        if product_id not in exclude_ids:
            ids.append(product_id)
        if len(ids) >= limit:
            break

    return ids


def _retrieve_with_numpy(query_vector, limit, exclude_ids):
    try:
        import numpy as np
    except ImportError:
        return []

    product_ids, embeddings = _load_numpy_artifacts()
    if product_ids is None or embeddings is None:
        return []

    scores = embeddings @ query_vector.reshape(-1)
    ranked_positions = np.argsort(-scores)

    ids = []
    for position in ranked_positions:
        product_id = int(product_ids[position])
        if product_id not in exclude_ids:
            ids.append(product_id)
        if len(ids) >= limit:
            break

    return ids


def _products_in_order(product_ids):
    products_by_id = Product.objects.in_bulk(product_ids)
    return [products_by_id[product_id] for product_id in product_ids if product_id in products_by_id]


def get_product_recommendations(anchor_product=None, limit=4, exclude_ids=None):
    exclude_ids = set(exclude_ids or [])
    if anchor_product:
        exclude_ids.add(anchor_product.id)

    query_vector = _load_anchor_vector(anchor_product)

    if query_vector is not None:
        product_ids = _retrieve_with_faiss(query_vector, limit, exclude_ids)
        if product_ids:
            products = _products_in_order(product_ids)
            return products, "faiss", explain_recommendations(anchor_product, products, "faiss")

        product_ids = _retrieve_with_numpy(query_vector, limit, exclude_ids)
        if product_ids:
            products = _products_in_order(product_ids)
            return products, "numpy", explain_recommendations(anchor_product, products, "numpy")

    products, source = fallback_product_recommendations(anchor_product, limit, exclude_ids)
    return products, source, explain_recommendations(anchor_product, products, source)
