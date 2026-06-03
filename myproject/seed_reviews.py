import os
import django
import random
from datetime import timedelta

from faker import Faker
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from shop.models import Product, Review

fake = Faker()
Faker.seed(2026)
random.seed(2026)

TOTAL_REVIEWS = 5500
UNIQUE_CUSTOMERS = 500

products = list(Product.objects.all())

if not products:
    raise Exception("No products found. Run product seed.py first.")

Review.objects.all().delete()

customers = []
while len(customers) < UNIQUE_CUSTOMERS:
    name = fake.unique.name()
    customers.append(name)

rating_comments = {
    5: [
        "Absolutely beautiful product. The quality feels premium and the finish is excellent.",
        "Loved it. The design looks luxurious and the product feels worth the price.",
        "Amazing purchase. The packaging, quality, and detailing were all impressive.",
        "Excellent quality. It looks even better in person than expected.",
        "Very elegant and premium. I would definitely recommend this product."
    ],
    4: [
        "Very good product overall. The quality is nice and it feels premium.",
        "Satisfied with the purchase. The product looks stylish and well made.",
        "Good quality and elegant design. Delivery and packaging were also nice.",
        "Worth buying. It has a premium feel and looks classy.",
        "Really liked it, though there is still a little room for improvement."
    ],
    3: [
        "Decent product. The design is nice, but I expected slightly better quality.",
        "Average experience. It looks good, but the finish could be improved.",
        "Not bad overall. The product is usable and looks fine.",
        "Fair quality for the price, but nothing extraordinary.",
        "Okay purchase. It matches the description, but I expected more."
    ],
    2: [
        "The product looks fine, but the quality was below my expectations.",
        "Could be better. The design is nice, but the finish did not feel very premium.",
        "Not fully satisfied. I expected better quality for this price.",
        "Below expectations. Packaging was fine, but the product could be improved.",
        "It is usable, but I would not call it a premium experience."
    ],
    1: [
        "Disappointed with the product. The quality did not match my expectations.",
        "Not recommended. The finish and overall feel could be much better.",
        "Poor experience. I expected a more premium product.",
        "Not satisfied with this purchase.",
        "The product did not feel worth the price."
    ]
}

product_weights = []

for i, product in enumerate(products):
    if i < 10:
        product_weights.append(random.randint(90, 160))
    elif i < 30:
        product_weights.append(random.randint(35, 80))
    else:
        product_weights.append(random.randint(5, 35))

reviews = []

for i in range(TOTAL_REVIEWS):
    product = random.choices(
        products,
        weights=product_weights,
        k=1
    )[0]

    rating = random.choices(
        [5, 4, 3, 2, 1],
        weights=[55, 28, 10, 5, 2],
        k=1
    )[0]

    customer_name = random.choice(customers)

    comment = random.choice(rating_comments[rating])

    comment = (
        f"{comment} "
        f"{fake.sentence(nb_words=random.randint(8, 16))} "
    )

    reviews.append(
        Review(
            product=product,
            customer_name=customer_name,
            rating=rating,
            comment=comment,
        )
    )

Review.objects.bulk_create(reviews, batch_size=500)

print(f"{TOTAL_REVIEWS} reviews added successfully.")
print(f"{UNIQUE_CUSTOMERS} unique customer names used.")