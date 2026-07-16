from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


CATEGORY_GROUPS = {
    "Everyday Fine Jewellery": [
        "Bangles", "Bracelets", "Earrings", "Gold Chains", "Gold Coins",
        "Kadas", "Mangalsutras", "Mangalsutra Bracelets", "Mangalsutra Chains",
        "Necklaces", "Nose Pins", "Nose Rings", "Nose Screws", "Pendants",
        "Rings", "Charms", "Anklets", "Toe Rings", "Anklet & Toe Ring Sets",
        "Armlets", "Waist Chains", "Hair Pins", "Maang Tikka", "Brooches",
        "Ear Cuffs", "Jhumkas", "Nath",
    ],
    "Men's Jewellery": [
        "Bracelets", "Studs", "Kadas", "Pendants", "Rings", "Cufflinks",
        "Chains", "Signet Rings", "Tie Pins", "Brooches",
    ],
    "Kids Jewellery": [
        "Earrings", "Pendants", "Necklaces", "Bracelets", "Nazariyas",
        "Bangles", "Anklets", "Rings", "Charms",
    ],
    "Platinum Jewellery": [
        "Rings", "Earrings", "Pendants", "Chains", "Bracelets",
        "Wedding Bands", "Solitaire Rings",
    ],
    "Gold Jewellery": [
        "Bangles", "Bracelets", "Chains", "Earrings", "Mangalsutras",
        "Necklaces", "Nose Pins", "Pendants", "Rings", "Kadas",
        "Waist Chains", "Toe Rings",
    ],
    "Diamond Jewellery": [
        "Bangles", "Bracelets", "Cufflinks", "Earrings", "Mangalsutras",
        "Necklaces", "Nose Pins", "Pendants", "Rings", "Tennis Bracelets",
        "Solitaire Rings", "Eternity Bands",
    ],
    "Gemstone Jewellery": [
        "Rings", "Earrings", "Pendants", "Necklaces", "Bracelets",
        "Cocktail Rings",
    ],
    "Pearl Jewellery": [
        "Earrings", "Necklaces", "Bracelets", "Pendants", "Brooches",
    ],
    "Bridal Collection": [
        "Necklace Sets", "Choker Sets", "Maang Tikka", "Nath", "Bajuband",
        "Bridal Sets",
    ],
    "Temple Jewellery": [
        "Necklaces", "Earrings", "Bangles", "Jhumkas", "Kadas", "Pendants",
    ],
    "Silver Jewellery": [
        "Rings", "Earrings", "Bracelets", "Anklets", "Chains", "Toe Rings",
        "Pendants",
    ],
    "Watches & Timepieces": [
        "Analog Watches", "Chronograph Watches", "Smart-look Fashion Watches",
        "Dress Watches", "Bracelet Watches",
    ],
    "Gifting & Combo Sets": [
        "Ring + Earring Combo", "Couple Bands", "Mother-Daughter Sets",
        "Festive Gift Boxes", "Bridal Gift Sets",
    ],
    "Accessories": [
        "Jewellery Boxes", "Organizers", "Keychains", "Jewellery Cleaning Cloths",
        "Travel Cases",
    ],
    "Western Necklaces": [
        "Statement Necklaces", "Layered Necklaces", "Chokers",
        "Pendant Necklaces",
    ],
    "Western Bracelets": [
        "Charm Bracelets", "Tennis Bracelets", "Cuff Bracelets",
        "Chain Bracelets",
    ],
    "Western Earrings": [
        "Hoop Earrings", "Huggie Earrings", "Ear Climbers", "Threader Earrings",
        "Studs",
    ],
    "Western Rings": [
        "Signet Rings", "Stackable Rings", "Cocktail Rings", "Promise Rings",
        "Solitaire Rings", "Eternity Bands", "Wedding Bands",
    ],
    "Men's Western": [
        "Chain Necklaces", "Signet Rings", "Tie Clips", "Cufflinks", "Bracelets",
    ],
}

CATEGORY_DISPLAY_ORDER = [
    "Everyday Fine Jewellery",
    "Bridal Collection",
    "Gold Jewellery",
    "Diamond Jewellery",
    "Platinum Jewellery",
    "Gemstone Jewellery",
    "Pearl Jewellery",
    "Silver Jewellery",
    "Temple Jewellery",
    "Men's Jewellery",
    "Kids Jewellery",
    "Western Necklaces",
    "Western Bracelets",
    "Western Earrings",
    "Western Rings",
    "Men's Western",
    "Watches & Timepieces",
    "Gifting & Combo Sets",
    "Accessories",
]

LEGACY_CATEGORY_NAMES = {
    "Shop By Category": "Everyday Fine Jewellery",
    "Kid's Jewellery": "Kids Jewellery",
    "Watches/Timepieces": "Watches & Timepieces",
    "Gifting/Combo Sets": "Gifting & Combo Sets",
}

NEW_SUBCATEGORIES = {
    ("Everyday Fine Jewellery", "Mangalsutra Bracelets"),
    ("Everyday Fine Jewellery", "Nose Rings"),
    ("Everyday Fine Jewellery", "Charms"),
    ("Kids Jewellery", "Nazariyas"),
}


def create_categories_and_backfill_products(apps, schema_editor):
    Category = apps.get_model("shop", "Category")
    Subcategory = apps.get_model("shop", "Subcategory")
    Product = apps.get_model("shop", "Product")

    category_lookup = {}
    subcategory_lookup = {}

    for display_order, category_name in enumerate(CATEGORY_DISPLAY_ORDER, start=1):
        legacy_name = next(
            (old for old, new in LEGACY_CATEGORY_NAMES.items() if new == category_name),
            None,
        )
        category = None

        if legacy_name:
            category = Category.objects.filter(name=legacy_name).first()

        if category is None:
            category = Category.objects.filter(name=category_name).first()

        if category is None:
            category = Category.objects.create(
                name=category_name,
                slug=slugify(category_name),
                description=f"{category_name} collection",
                display_order=display_order,
            )
        else:
            category.name = category_name
            category.slug = slugify(category_name)
            category.description = category.description or f"{category_name} collection"
            category.display_order = display_order
            category.save(update_fields=["name", "slug", "description", "display_order"])

        category_lookup[category_name] = category

        for sub_order, subcategory_name in enumerate(CATEGORY_GROUPS[category_name], start=1):
            subcategory, _ = Subcategory.objects.get_or_create(
                category=category,
                slug=slugify(subcategory_name),
                defaults={
                    "name": subcategory_name,
                    "description": f"{subcategory_name} in {category_name}",
                    "display_order": sub_order,
                    "is_new": (category_name, subcategory_name) in NEW_SUBCATEGORIES,
                },
            )
            subcategory.name = subcategory_name
            subcategory.display_order = sub_order
            subcategory.is_new = (category_name, subcategory_name) in NEW_SUBCATEGORIES
            subcategory.save(update_fields=["name", "display_order", "is_new"])
            subcategory_lookup[(category_name, subcategory_name)] = subcategory

    fallback_category = category_lookup["Everyday Fine Jewellery"]
    fallback_subcategory = subcategory_lookup[("Everyday Fine Jewellery", "Rings")]

    for product in Product.objects.select_related("category").all():
        category_name = fallback_category.name
        if product.category_id and product.category:
            category_name = LEGACY_CATEGORY_NAMES.get(product.category.name, product.category.name)

        if category_name not in category_lookup:
            category_name = fallback_category.name

        subcategory_name = product.subcategory or fallback_subcategory.name
        if (category_name, subcategory_name) not in subcategory_lookup:
            subcategory_name = CATEGORY_GROUPS[category_name][0]

        category = category_lookup[category_name]
        subcategory = subcategory_lookup[(category_name, subcategory_name)]

        product.primary_category_id = category.id
        product.primary_subcategory_id = subcategory.id
        product.save(update_fields=["primary_category", "primary_subcategory"])
        product.categories.add(category)
        product.subcategories.add(subcategory)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0035_product_carat_weight_product_chain_style_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="category",
            options={"ordering": ["display_order", "name"], "verbose_name_plural": "Categories"},
        ),
        migrations.AddField(
            model_name="category",
            name="display_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="Subcategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField()),
                ("description", models.TextField(blank=True, default="")),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_new", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subcategories",
                        to="shop.category",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Subcategories",
                "ordering": ["display_order", "name"],
                "unique_together": {("category", "slug")},
            },
        ),
        migrations.AddField(
            model_name="product",
            name="primary_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_products",
                to="shop.category",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="primary_subcategory",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_products",
                to="shop.subcategory",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="categories",
            field=models.ManyToManyField(blank=True, related_name="classified_products", to="shop.category"),
        ),
        migrations.AddField(
            model_name="product",
            name="subcategories",
            field=models.ManyToManyField(blank=True, related_name="products", to="shop.subcategory"),
        ),
        migrations.RunPython(create_categories_and_backfill_products, reverse_noop),
        migrations.AlterField(
            model_name="product",
            name="primary_category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_products",
                to="shop.category",
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="primary_subcategory",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_products",
                to="shop.subcategory",
            ),
        ),
        migrations.RemoveField(
            model_name="product",
            name="category",
        ),
        migrations.RemoveField(
            model_name="product",
            name="subcategory",
        ),
        migrations.AlterField(
            model_name="product",
            name="categories",
            field=models.ManyToManyField(blank=True, related_name="products", to="shop.category"),
        ),
    ]
