import random
import re
import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from shop.models import Product


METAL_FACTORS = {
    "Gold": 1.00,
    "Rose Gold": 1.04,
    "White Gold": 1.08,
    "Silver": 0.24,
    "Platinum": 1.36,
}
GEMSTONE_FACTORS = {
    "None": 0.78,
    "Emerald": 1.08,
    "Ruby": 1.12,
    "Diamond": 1.34,
}
FINISH_FACTORS = {
    "Polished": 1.00,
    "Matte": 1.02,
    "Antique/Oxidized": 1.06,
}


def normalized_metal(product):
    value = f"{product.material} {product.metal_color}".lower()
    if "silver" in value:
        return "Silver"
    if "platinum" in value:
        return "Platinum"
    if "rose" in value:
        return "Rose Gold"
    if "white" in value:
        return "White Gold"
    return "Gold"


def normalized_gemstone(product):
    value = (product.stone_type or "").lower()
    if "diamond" in value or "solitaire" in value:
        return "Diamond"
    if "ruby" in value:
        return "Ruby"
    if "emerald" in value:
        return "Emerald"
    return "None"


def normalized_finish(product):
    value = (product.finish or "").lower()
    if "oxid" in value or "antique" in value:
        return "Antique/Oxidized"
    if "matte" in value or "brushed" in value:
        return "Matte"
    return "Polished"


def variant_price(base, base_attributes, attributes):
    factor = 1.0
    for axis, factors in (
        ("metal", METAL_FACTORS),
        ("gemstone", GEMSTONE_FACTORS),
        ("finish", FINISH_FACTORS),
    ):
        if axis in attributes:
            old_factor = factors[base_attributes[axis]]
            factor *= factors[attributes[axis]] / old_factor
    return max(500, int(round((base.price * factor) / 100.0) * 100))


def apply_attributes(product, attributes):
    metal = attributes.get("metal")
    if metal:
        product.metal_color = metal
        if metal == "Silver":
            product.material = "Sterling Silver (925)"
        elif metal == "Platinum":
            product.material = "Platinum 950"
        else:
            purity = product.purity or "18K"
            product.material = f"{purity} {metal}"

    gemstone = attributes.get("gemstone")
    if gemstone:
        product.stone_type = "" if gemstone == "None" else gemstone

    finish = attributes.get("finish")
    if finish:
        product.finish = {
            "Polished": "High Polish",
            "Matte": "Matte",
            "Antique/Oxidized": "Oxidized",
        }[finish]


def design_name(product):
    name = re.sub(
        r"\b(?:Sterling Silver \(925\)|Gold Vermeil|\d+K Yellow Gold|Platinum 950)\b",
        "",
        product.name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"\s+with\s+.+?\s+Accent", "", name, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", name).strip(" ,-" )


class Command(BaseCommand):
    help = "Create a curated, repeat-safe set of metal, gemstone, and finish variants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--groups",
            type=int,
            default=8,
            help="Maximum number of base products to turn into variant groups.",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--add-more",
            action="store_true",
            help="Create another curated batch even if this command has already seeded variants.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(20260713)
        max_groups = max(1, options["groups"])
        existing_seeded = Product.objects.filter(
            sku__startswith="AUR-VG-",
            variant_group__isnull=False,
        ).exists()
        if existing_seeded and not options["add_more"]:
            self.stdout.write(
                self.style.WARNING(
                    "Catalog variants have already been seeded; no changes made. "
                    "Use --add-more to intentionally create another batch."
                )
            )
            return

        created_count = 0
        grouped_count = 0
        axis_counts = {"metal": 0, "gemstone": 0, "finish": 0}
        used_base_ids = set()

        plans = [
            {
                "label": "diamond ring metal",
                "filters": {"primary_subcategory__name__in": ["Rings", "Signet Rings"], "stone_type__icontains": "diamond", "material__icontains": "gold"},
                "axes": {"metal": ["Gold", "Rose Gold", "White Gold", "Platinum"]},
            },
            {
                "label": "solitaire ring metal and gemstone",
                "filters": {"primary_subcategory__name__in": ["Rings", "Signet Rings"], "stone_type__icontains": "solitaire", "material__icontains": "gold"},
                "axes": {"metal": ["Gold", "White Gold", "Platinum"], "gemstone": ["Diamond", "Ruby", "Emerald"]},
            },
            {
                "label": "pendant gemstone",
                "filters": {"primary_subcategory__name__icontains": "pendant", "stone_type__in": ["", "Diamond", "Ruby", "Emerald"]},
                "axes": {"gemstone": ["Diamond", "Ruby", "Emerald", "None"]},
            },
            {
                "label": "bridal set metal",
                "filters": {"primary_category__name": "Bridal Collection"},
                "axes": {"metal": ["Gold", "Rose Gold", "White Gold"]},
            },
            {
                "label": "classic band metal",
                "filters": {"primary_subcategory__name__in": ["Rings", "Signet Rings"], "stone_type": "", "material__icontains": "gold"},
                "axes": {"metal": ["Gold", "Rose Gold", "White Gold", "Platinum"]},
            },
            {
                "label": "silver bracelet finish",
                "filters": {"primary_subcategory__name__icontains": "bracelet", "material__icontains": "silver"},
                "axes": {"finish": ["Polished", "Matte", "Antique/Oxidized"]},
            },
            {
                "label": "silver earring finish",
                "filters": {"primary_subcategory__name__icontains": "earring", "material__icontains": "silver"},
                "axes": {"finish": ["Polished", "Matte", "Antique/Oxidized"]},
            },
            {
                "label": "men's ring metal",
                "filters": {"primary_category__name__in": ["Men's", "Men's Jewellery", "Men's Western"], "primary_subcategory__name__in": ["Rings", "Signet Rings"], "purity__in": ["18K", "22K"]},
                "axes": {"metal": ["Gold", "Rose Gold", "White Gold", "Platinum"]},
            },
            {
                "label": "necklace gemstone",
                "filters": {"primary_subcategory__name__icontains": "necklace", "stone_type__in": ["", "Diamond", "Ruby", "Emerald"]},
                "axes": {"gemstone": ["Diamond", "Ruby", "Emerald", "None"]},
            },
        ]

        for plan in plans:
            if grouped_count >= max_groups:
                break

            base = (
                Product.objects.filter(variant_group__isnull=True, **plan["filters"])
                .exclude(pk__in=used_base_ids)
                .order_by("id")
                .first()
            )
            if not base:
                self.stdout.write(self.style.WARNING(f"Skipped {plan['label']}: no matching product."))
                continue

            used_base_ids.add(base.id)
            axes = plan["axes"]
            base_values = {
                "metal": normalized_metal(base),
                "gemstone": normalized_gemstone(base),
                "finish": normalized_finish(base),
            }
            base_attributes = {axis: base_values[axis] for axis in axes}

            combinations = [base_attributes]
            for axis, values in axes.items():
                for value in values:
                    candidate = dict(base_attributes)
                    candidate[axis] = value
                    if candidate not in combinations:
                        combinations.append(candidate)

            group_id = uuid.uuid5(uuid.NAMESPACE_URL, f"aurum-variant-base-{base.id}")
            base.variant_group = group_id
            base.variant_attributes = base_attributes
            base.sku = base.sku or f"AUR-VG-{base.id}-BASE"

            if options["dry_run"]:
                self.stdout.write(f"Would group #{base.id} {base.name}: {combinations}")
                grouped_count += 1
                for axis in axes:
                    axis_counts[axis] += 1
                continue

            base.save(update_fields=["variant_group", "variant_attributes", "sku"])
            shared_values = {
                field.name: getattr(base, field.name)
                for field in Product._meta.concrete_fields
                if field.name not in {
                    "id", "name", "slug", "sku", "price", "stock", "variant_group",
                    "variant_attributes", "material", "metal_color", "stone_type", "finish",
                }
            }
            categories = list(base.categories.all())
            subcategories = list(base.subcategories.all())
            tags = list(base.tags.all())

            for index, attributes in enumerate(combinations[1:], start=1):
                attribute_label = ", ".join(attributes.values())
                slug_suffix = slugify("-".join(attributes.values()))
                slug = f"{(base.slug or slugify(base.name))[:190]}-variant-{slug_suffix}-{base.id}"
                name = f"{design_name(base)} - {attribute_label}"[:200]
                variant = Product(
                    **shared_values,
                    name=name,
                    slug=slug[:240],
                    sku=f"AUR-VG-{base.id}-{index:02d}",
                    price=variant_price(base, base_attributes, attributes),
                    stock=random.randint(0, 35),
                    material=base.material,
                    metal_color=base.metal_color,
                    stone_type=base.stone_type,
                    finish=base.finish,
                    variant_group=group_id,
                    variant_attributes=attributes,
                )
                apply_attributes(variant, attributes)
                variant.save()
                variant.categories.set(categories)
                variant.subcategories.set(subcategories)
                variant.tags.set(tags)
                created_count += 1

            grouped_count += 1
            for axis in axes:
                axis_counts[axis] += 1
            self.stdout.write(self.style.SUCCESS(f"Created {plan['label']} variants from #{base.id}."))

        if options["dry_run"]:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run complete; no changes saved."))
            return

        self.stdout.write(self.style.SUCCESS("\nVariation seed summary"))
        self.stdout.write(f"New variant products created: {created_count}")
        self.stdout.write(f"Base products grouped: {grouped_count}")
        self.stdout.write(f"Groups using metal: {axis_counts['metal']}")
        self.stdout.write(f"Groups using gemstone: {axis_counts['gemstone']}")
        self.stdout.write(f"Groups using finish: {axis_counts['finish']}")
