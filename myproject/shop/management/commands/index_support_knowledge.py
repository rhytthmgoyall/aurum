from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from shop.models import Product


class Command(BaseCommand):
    help = "Index AURUM products and public support docs into Qdrant"

    def handle(self, *args, **options):
        embedding_model = SentenceTransformer(settings.RAG_EMBEDDING_MODEL)
        qdrant = QdrantClient(url=settings.QDRANT_URL, timeout=60.0)
        collection = settings.QDRANT_COLLECTION

        self.ensure_collection(qdrant, collection)

        points = []
        points.extend(self.build_product_points(embedding_model))
        points.extend(self.build_support_doc_points(embedding_model))

        if points:
            qdrant.upsert(collection_name=collection, points=points)

        self.stdout.write(
            self.style.SUCCESS(f"Indexed {len(points)} AURUM knowledge chunks into Qdrant.")
        )

    def ensure_collection(self, qdrant, collection):
        if qdrant.collection_exists(collection):
            qdrant.delete_collection(collection)

        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=settings.RAG_VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )

    def build_product_points(self, embedding_model):
        points = []

        products = (
            Product.objects
            .select_related("primary_category", "primary_subcategory")
            .prefetch_related("categories", "subcategories", "tags", "reviews")
            .all()
        )

        for product in products:
            text = self.build_product_text(product)
            vector = embedding_model.encode(text, normalize_embeddings=True).tolist()

            points.append(
                PointStruct(
                    id=str(uuid5(NAMESPACE_URL, f"aurum-product-{product.id}")),
                    vector=vector,
                    payload={
                        "source_type": "product",
                        "source_id": product.id,
                        "title": product.name,
                        "source": f"product:{product.id}",
                        "content": text,
                        "url": f"/product/{product.id}/",
                        "price": product.price,
                        "stock": product.stock,
                        "category": product.primary_category.name if product.primary_category else "",
                        "material": product.material,
                        "occasion": product.occasion,
                        "who_for": product.who_for,
                        "price_range": product.price_range,
                    },
                )
            )

        return points

    def build_product_text(self, product):
        tags = ", ".join(tag.name for tag in product.tags.all())
        category = product.primary_category.name if product.primary_category else ""
        subcategory = product.primary_subcategory.name if product.primary_subcategory else ""
        reviews = product.reviews.all()
        avg_rating = None

        if reviews:
            ratings = [review.rating for review in reviews]
            avg_rating = round(sum(ratings) / len(ratings), 1)

        parts = [
            f"Product: {product.name}.",
            f"Category: {category}.",
            f"Subcategory: {subcategory}.",
            f"Material: {product.material}.",
            f"Occasion: {product.occasion}.",
            f"For: {product.who_for}.",
            f"Price: INR {product.price}.",
            f"Price range: {product.price_range}.",
            f"Stock: {product.stock}.",
            f"Tags: {tags}.",
            f"Description: {product.description}.",
        ]

        if product.is_new:
            parts.append("This is a new arrival.")

        if avg_rating:
            parts.append(f"Average customer rating: {avg_rating} out of 5.")

        return " ".join(part for part in parts if part and part.strip())

    def build_support_doc_points(self, embedding_model):
        docs_dir = Path(settings.BASE_DIR) / "shop" / "rag_docs"
        if not docs_dir.exists():
            raise CommandError(f"Knowledge docs folder does not exist: {docs_dir}")

        points = []

        for path in sorted(docs_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            chunks = self.chunk_text(text)

            for index, chunk in enumerate(chunks, start=1):
                vector = embedding_model.encode(chunk, normalize_embeddings=True).tolist()

                points.append(
                    PointStruct(
                        id=str(uuid5(NAMESPACE_URL, f"aurum-doc-{path.name}-{index}")),
                        vector=vector,
                        payload={
                            "source_type": "support_doc",
                            "source_id": path.name,
                            "title": path.stem.replace("-", " ").title(),
                            "source": f"{path.name}#{index}",
                            "content": chunk,
                            "url": "",
                        },
                    )
                )

        return points

    def chunk_text(self, text, max_chars=1800):
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        current = ""

        for paragraph in paragraphs:
            next_text = f"{current}\n\n{paragraph}".strip()

            if current and len(next_text) > max_chars:
                chunks.append(current)
                current = paragraph
            else:
                current = next_text

        if current:
            chunks.append(current)

        return chunks
