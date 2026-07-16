from collections import defaultdict
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.models import Product, ProductEmbedding, ProductInteraction
from shop.recommender import ARTIFACT_DIR, FAISS_INDEX_PATH, PRODUCT_EMBEDDINGS_PATH, PRODUCT_IDS_PATH


class Command(BaseCommand):
    help = "Train a TensorFlow two-tower recommender and build FAISS retrieval artifacts."

    def add_arguments(self, parser):
        parser.add_argument("--epochs", type=int, default=12)
        parser.add_argument("--embedding-dim", type=int, default=32)
        parser.add_argument("--negative-samples", type=int, default=4)
        parser.add_argument("--model-version", default="two_tower_v1")

    def handle(self, *args, **options):
        try:
            import numpy as np
            import tensorflow as tf
        except ImportError as error:
            raise CommandError(
                "TensorFlow training dependencies are missing. Install them with "
                "`pip install -r requirements-ml.txt` from the myproject folder."
            ) from error

        products = list(Product.objects.order_by("id"))
        if len(products) < 2:
            raise CommandError("Need at least two products to train recommendations.")

        product_ids = np.array([product.id for product in products], dtype="int64")
        product_index = {product.id: index for index, product in enumerate(products)}

        actor_product_weights = self._load_positive_interactions()
        if not actor_product_weights:
            raise CommandError(
                "No positive product interactions found. Visit product pages or add "
                "items to cart first so the model has behavior data."
            )

        actor_keys = sorted(actor_product_weights)
        actor_index = {actor_key: index for index, actor_key in enumerate(actor_keys)}

        actor_inputs = []
        product_inputs = []
        labels = []
        sample_weights = []
        all_product_indexes = set(range(len(products)))
        negative_samples = options["negative_samples"]

        for actor_key, product_weights in actor_product_weights.items():
            positives = {product_index[product_id] for product_id in product_weights if product_id in product_index}
            negatives = list(all_product_indexes - positives)

            if not positives or not negatives:
                continue

            for product_id, weight in product_weights.items():
                if product_id not in product_index:
                    continue

                actor_inputs.append(actor_index[actor_key])
                product_inputs.append(product_index[product_id])
                labels.append(1.0)
                sample_weights.append(max(float(weight), 1.0))

                for negative_index in random.sample(negatives, min(negative_samples, len(negatives))):
                    actor_inputs.append(actor_index[actor_key])
                    product_inputs.append(negative_index)
                    labels.append(0.0)
                    sample_weights.append(1.0)

        if not labels:
            raise CommandError("Not enough interaction variety to build training pairs.")

        actor_inputs = np.array(actor_inputs, dtype="int32")
        product_inputs = np.array(product_inputs, dtype="int32")
        labels = np.array(labels, dtype="float32")
        sample_weights = np.array(sample_weights, dtype="float32")

        model = self._build_two_tower_model(
            tf=tf,
            actor_count=len(actor_keys),
            product_count=len(products),
            embedding_dim=options["embedding_dim"],
        )

        model.fit(
            {"actor": actor_inputs, "product": product_inputs},
            labels,
            sample_weight=sample_weights,
            epochs=options["epochs"],
            verbose=1,
        )

        product_embeddings = model.get_layer("product_embedding").get_weights()[0].astype("float32")
        product_embeddings = self._normalize(np, product_embeddings)

        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        np.save(PRODUCT_IDS_PATH, product_ids)
        np.save(PRODUCT_EMBEDDINGS_PATH, product_embeddings)
        self._write_faiss_index(product_embeddings)
        self._save_embeddings(product_ids, product_embeddings, options["model_version"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Trained {options['model_version']} with {len(actor_keys)} actors, "
                f"{len(products)} products, and {len(labels)} training rows."
            )
        )

    def _load_positive_interactions(self):
        actor_product_weights = defaultdict(lambda: defaultdict(float))

        interactions = (
            ProductInteraction.objects.exclude(event_type=ProductInteraction.REMOVE_FROM_CART)
            .select_related("user", "product")
            .order_by("created_at")
        )

        for interaction in interactions:
            if interaction.user_id:
                actor_key = f"user:{interaction.user_id}"
            elif interaction.session_key:
                actor_key = f"session:{interaction.session_key}"
            else:
                continue

            actor_product_weights[actor_key][interaction.product_id] += max(interaction.weight, 0.0)

        return {
            actor_key: {
                product_id: weight
                for product_id, weight in product_weights.items()
                if weight > 0
            }
            for actor_key, product_weights in actor_product_weights.items()
        }

    def _build_two_tower_model(self, tf, actor_count, product_count, embedding_dim):
        actor_input = tf.keras.Input(shape=(), dtype=tf.int32, name="actor")
        product_input = tf.keras.Input(shape=(), dtype=tf.int32, name="product")

        actor_embedding = tf.keras.layers.Embedding(
            actor_count,
            embedding_dim,
            name="actor_embedding",
        )(actor_input)
        product_embedding = tf.keras.layers.Embedding(
            product_count,
            embedding_dim,
            name="product_embedding",
        )(product_input)

        score = tf.keras.layers.Dot(axes=1, normalize=True)([actor_embedding, product_embedding])
        output = tf.keras.layers.Activation("sigmoid")(score)

        model = tf.keras.Model(
            inputs={"actor": actor_input, "product": product_input},
            outputs=output,
        )
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.01),
            loss="binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    def _normalize(self, np, embeddings):
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return embeddings / norms

    def _write_faiss_index(self, product_embeddings):
        try:
            import faiss
        except ImportError:
            self.stdout.write("FAISS is not installed; saved NumPy embeddings only.")
            return

        index = faiss.IndexFlatIP(product_embeddings.shape[1])
        index.add(product_embeddings)
        faiss.write_index(index, str(FAISS_INDEX_PATH))

    def _save_embeddings(self, product_ids, product_embeddings, model_version):
        rows = [
            ProductEmbedding(
                product_id=int(product_id),
                vector=product_embeddings[index].tolist(),
                model_version=model_version,
            )
            for index, product_id in enumerate(product_ids)
        ]

        with transaction.atomic():
            ProductEmbedding.objects.all().delete()
            ProductEmbedding.objects.bulk_create(rows, batch_size=500)
