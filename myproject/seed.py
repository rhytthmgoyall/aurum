import os
import random
import uuid

import django
from faker import Faker

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from django.utils.text import slugify
from shop.models import Category, Product, Subcategory, Tag


fake = Faker("en_IN")
Faker.seed(2026)
random.seed(2026)

TARGET_PRODUCT_COUNT = 3000
MIN_PER_PAIR = 8
MAX_PER_PAIR = 65

CATEGORY_GROUPS = {
    "Everyday Fine Jewellery": [
        "Bangles", "Bracelets", "Earrings", "Gold Chains", "Gold Coins",
        "Kadas", "Mangalsutras", "Mangalsutra Bracelets", "Mangalsutra Chains",
        "Necklaces", "Nose Pins", "Nose Rings", "Nose Screws", "Pendants",
        "Rings", "Charms", "Anklets", "Toe Rings", "Anklet & Toe Ring Sets",
        "Armlets", "Waist Chains", "Hair Pins", "Maang Tikka", "Brooches",
        "Ear Cuffs", "Jhumkas", "Nath", "Gold", "Platinum", "Gemstone",
        "Silver", "Pearl", "Diamond", "Temple",
    ],
    "Bridal Collection": [
        "Necklace Sets", "Choker Sets", "Maang Tikka", "Nath", "Bajuband",
        "Bridal Sets",
    ],
    "Men's": [
        "Bracelets", "Studs", "Kadas", "Pendants", "Rings", "Cufflinks",
        "Chains", "Signet Rings", "Tie Pins", "Brooches",
    ],
    "Kids": [
        "Earrings", "Pendants", "Necklaces", "Bracelets", "Nazariyas",
        "Bangles", "Anklets", "Rings", "Charms",
    ],
    "Western": ["Necklaces", "Bracelets", "Earrings", "Rings", "Men's"],
    "Timepieces": [
        "Analog Watches", "Chronograph Watches", "Smart-look Fashion Watches",
        "Dress Watches", "Bracelet Watches",
    ],
    "Accessories": [
        "Jewellery Boxes", "Organizers", "Keychains", "Jewellery Cleaning Cloths",
        "Travel Cases",
    ],
    "Gifting & Combo Sets": [
        "Ring + Earring Combo", "Couple Bands", "Mother-Daughter Sets",
        "Festive Gift Boxes", "Bridal Gift Sets",
    ],
}

CATEGORY_DISPLAY_ORDER = [
    "Everyday Fine Jewellery",
    "Bridal Collection",
    "Men's",
    "Kids",
    "Western",
    "Timepieces",
    "Accessories",
    "Gifting & Combo Sets",
]

NEW_SUBCATEGORIES = {
    ("Everyday Fine Jewellery", "Mangalsutra Bracelets"),
    ("Everyday Fine Jewellery", "Nose Rings"),
    ("Everyday Fine Jewellery", "Charms"),
    ("Kids", "Nazariyas"),
}

OCCASIONS = [
    "bridal", "festive", "daily wear", "office", "gifting", "anniversary",
    "engagement", "Diwali", "Karva Chauth", "Raksha Bandhan",
]

INDIAN_STYLES = [
    "Antique", "Temple", "Kundan", "Polki", "Meenakari", "Nakshi",
    "Filigree", "Heritage", "Peacock", "Floral", "Traditional", "Royal",
    "Handcrafted", "Regal", "Jaipuri",
]

WESTERN_STYLES = [
    "Minimalist", "Modern", "Classic", "Layered", "Statement", "Everyday",
    "Vintage", "Sleek", "Geometric", "Delicate", "Personalized", "Zodiac",
    "Birthstone", "Art Deco",
]

FINISHES = [
    "High Polish", "Matte", "Antique", "Oxidized", "Textured", "Brushed",
    "Rhodium Plated",
]

SETTINGS = ["Prong", "Bezel", "Pave", "Channel", "Halo", "Cluster"]

CHAIN_STYLES = [
    "Cuban Link", "Paperclip", "Figaro", "Rope", "Box Chain", "Snake Chain",
]

WESTERN_NAME_STYLES = {
    "Necklaces": ["Statement Necklace", "Layered Necklace", "Choker Necklace", "Pendant Necklace"],
    "Bracelets": ["Charm Bracelet", "Tennis Bracelet", "Cuff Bracelet", "Chain Bracelet"],
    "Earrings": ["Hoop Earrings", "Huggie Earrings", "Ear Climbers", "Threader Earrings", "Stud Earrings"],
    "Rings": ["Signet Ring", "Stackable Ring", "Cocktail Ring", "Promise Ring", "Solitaire Ring", "Eternity Band", "Wedding Band"],
    "Men's": ["Chain Necklace", "Signet Ring", "Tie Clip", "Cufflinks", "Bracelet"],
}

ENAMEL_COLORS = ["Red", "Green", "Blue", "Multicolor", "None"]

REGIONAL_STYLES = [
    "South Indian", "Rajasthani", "Bengali", "Marwari", "Kundan-Jaipuri",
]

STONES = [
    "Ruby", "Emerald", "Sapphire", "Topaz", "Amethyst", "Garnet", "Opal",
    "Pearl", "Diamond", "Onyx", "Moonstone", "Aquamarine", "Citrine",
    "Navratna", "Kundan", "Polki", "Zircon", "Solitaire", "Peridot",
    "Turquoise",
]

STONE_CUTS = [
    "Round Brilliant", "Princess", "Emerald Cut", "Pear", "Marquise", "Oval",
    "Cushion",
]

BIRTHSTONES = {
    "January": "Garnet",
    "February": "Amethyst",
    "March": "Aquamarine",
    "April": "Diamond",
    "May": "Emerald",
    "June": "Pearl",
    "July": "Ruby",
    "August": "Peridot",
    "September": "Sapphire",
    "October": "Opal",
    "November": "Topaz",
    "December": "Turquoise",
}

FINE_GOLD_RATES = {
    "22K Yellow Gold": 6800,
    "22K Rose Gold": 6800,
    "22K White Gold": 6800,
    "18K Yellow Gold": 5600,
    "18K Rose Gold": 5600,
    "18K White Gold": 5600,
    "14K Yellow Gold": 4400,
    "14K Rose Gold": 4400,
    "14K White Gold": 4400,
    "Platinum": 3200,
}

FASHION_PRICE_BANDS = {
    "Stainless Steel": (499, 2499),
    "Sterling Silver (925)": (999, 5999),
    "Gold Vermeil": (1499, 7999),
    "Titanium": (799, 3499),
}

PRICE_RANGES = [
    ("under Rs.999", 0, 998),
    ("Rs.999-4999", 999, 4999),
    ("Rs.4999-15000", 4999, 15000),
    ("Rs.15000+", 15001, 10_000_000),
]

WESTERN_COLLECTIONS = [
    "Minimalist/Everyday", "Birthstone Jewellery", "Personalized",
    "Wedding & Engagement", "Party/Statement",
]

ACCESSORY_MATERIALS = ["velvet", "leatherette", "microfiber", "metal", "wood"]
WATCH_MATERIALS = ["stainless steel", "leather strap", "mesh strap", "ceramic look"]


def is_western_category(category_name):
    return category_name == "Western"


def is_accessory(category_name):
    return category_name == "Accessories"


def is_watch(category_name):
    return category_name == "Timepieces"


def is_combo(category_name):
    return category_name == "Gifting & Combo Sets"


def get_who_for(category_name, subcategory):
    if "Kid" in category_name:
        return "kids"
    if category_name == "Men's" or subcategory in ["Men's", "Cufflinks", "Tie Clips", "Tie Pins"]:
        return random.choice(["men", "unisex"])
    if is_western_category(category_name) and subcategory in ["Men's", "Rings", "Bracelets"]:
        return random.choice(["women", "men", "unisex"])
    return "women"


def choose_material(category_name, subcategory):
    if is_accessory(category_name):
        return random.choice(ACCESSORY_MATERIALS)
    if is_watch(category_name):
        return random.choice(WATCH_MATERIALS)
    if subcategory == "Gold":
        return random.choice(["22K Yellow Gold", "22K Yellow Gold", "18K Yellow Gold"])
    if subcategory == "Platinum":
        return "Platinum"
    if subcategory == "Diamond":
        return random.choice(["18K Yellow Gold", "18K White Gold", "14K Rose Gold", "Platinum"])
    if subcategory == "Gemstone":
        return random.choice(["18K Yellow Gold", "18K Rose Gold", "Sterling Silver (925)"])
    if subcategory == "Silver":
        return "Sterling Silver (925)"
    if subcategory == "Pearl":
        return random.choice(["18K Yellow Gold", "Sterling Silver (925)", "Gold Vermeil"])
    if subcategory == "Temple":
        return random.choice(["22K Yellow Gold", "22K Yellow Gold", "18K Yellow Gold"])
    if is_western_category(category_name):
        if subcategory == "Rings":
            return random.choice(["14K Yellow Gold", "14K Rose Gold", "18K White Gold", "Platinum"])
        return random.choice(["Sterling Silver (925)", "Gold Vermeil", "Stainless Steel", "Titanium", "14K Rose Gold"])
    if category_name == "Bridal Collection":
        return random.choice(["22K Yellow Gold", "22K Yellow Gold", "18K Yellow Gold"])
    if "Gold" in subcategory or subcategory in ["Mangalsutras", "Kadas", "Bangles"]:
        return random.choice(["22K Yellow Gold", "18K Yellow Gold"])
    return random.choice(["22K Yellow Gold", "18K Yellow Gold", "Sterling Silver (925)", "Gold Vermeil"])


def split_material(material):
    if material == "Platinum":
        return "", "Platinum"
    if material == "Sterling Silver (925)":
        return "925", "Silver"
    if material in ["Gold Vermeil", "Stainless Steel", "Titanium"]:
        return "", material
    parts = material.split(" ", 1)
    if len(parts) == 2 and parts[0].endswith("K"):
        return parts[0], parts[1]
    return "", material


def choose_stone(category_name, subcategory, material):
    if is_accessory(category_name) or is_watch(category_name):
        return None
    if "Gold Coins" in subcategory:
        return None
    if subcategory == "Diamond":
        return random.choice(["Diamond", "Solitaire", "Zircon"])
    if subcategory == "Gemstone":
        return random.choice(["Ruby", "Emerald", "Sapphire", "Topaz", "Amethyst", "Garnet", "Aquamarine", "Citrine", "Peridot", "Turquoise"])
    if subcategory == "Pearl":
        return "Pearl"
    if subcategory == "Temple":
        return random.choice(["Ruby", "Emerald", "Kundan", "Polki", "Navratna"])
    if "Birthstone" in category_name:
        return random.choice(list(BIRTHSTONES.values()))
    if random.random() < 0.62:
        return random.choice(STONES)
    return None


def choose_weight(subcategory):
    if "Ring" in subcategory or "Band" in subcategory:
        return round(random.uniform(2, 6), 2)
    if "Earring" in subcategory or subcategory in ["Studs", "Jhumkas", "Ear Cuffs", "Ear Climbers", "Threader Earrings"]:
        return round(random.uniform(1.5, 8), 2)
    if "Bangle" in subcategory or "Kada" in subcategory:
        return round(random.uniform(15, 35), 2)
    if "Necklace" in subcategory or "Choker" in subcategory or "Mangalsutra" in subcategory:
        return round(random.uniform(15, 45), 2)
    if "Bracelet" in subcategory:
        return round(random.uniform(5, 20), 2)
    if "Pendant" in subcategory or "Charm" in subcategory:
        return round(random.uniform(2, 10), 2)
    if "Chain" in subcategory:
        return round(random.uniform(8, 25), 2)
    return round(random.uniform(2, 18), 2)


def choose_size_detail(subcategory):
    if "Ring" in subcategory or "Band" in subcategory:
        return f"Size {random.randint(5, 13)}"
    if "Bangle" in subcategory or "Kada" in subcategory:
        return f'{random.choice(["2.2", "2.4", "2.6", "2.8"])} inch'
    if "Necklace" in subcategory or "Chain" in subcategory or "Choker" in subcategory:
        return f'{random.choice([14, 16, 18, 20, 24])} inch'
    if "Bracelet" in subcategory or "Anklet" in subcategory:
        return f'{random.choice(["6.5", "7", "7.5", "8"])} inch'
    if "Earring" in subcategory or subcategory in ["Studs", "Jhumkas", "Ear Cuffs", "Ear Climbers", "Threader Earrings"]:
        return random.choice(["Stud", "Short Drop", "Long Drop", "Jhumka-length"])
    if "Watch" in subcategory:
        return f"{random.randint(32, 44)}mm"
    return ""


def is_adjustable(subcategory, category_name):
    if subcategory in ["Rings", "Stackable Rings", "Cocktail Rings", "Charm Bracelets", "Cuff Bracelets", "Anklets", "Kadas"]:
        return random.random() < 0.45
    if is_western_category(category_name) and subcategory in ["Chokers", "Layered Necklaces", "Chain Bracelets"]:
        return random.random() < 0.35
    return False


def choose_collection(category_name, subcategory, occasion, stone):
    if category_name == "Bridal Collection":
        return "Bridal"
    if category_name == "Temple Jewellery":
        return "Temple"
    if occasion == "engagement" or subcategory in ["Promise Rings", "Solitaire Rings", "Wedding Bands"]:
        return "Wedding & Engagement"
    if is_western_category(category_name):
        if stone in BIRTHSTONES.values() and random.random() < 0.45:
            return "Birthstone Jewellery"
        return random.choice(WESTERN_COLLECTIONS)
    if occasion in ["Diwali", "Karva Chauth"]:
        return "Festive"
    return ""


def choose_engraving_text(collection):
    if collection != "Personalized":
        return ""
    return random.choice([
        fake.first_name(),
        fake.bothify(text="?").upper(),
        fake.date(pattern="%d.%m.%Y"),
    ])


def choose_carat_weight(stone):
    if not stone:
        return None
    if stone in ["Diamond", "Solitaire", "Ruby", "Emerald", "Sapphire"]:
        return round(random.uniform(0.25, 2.0), 2)
    if stone in ["Topaz", "Amethyst", "Garnet", "Aquamarine", "Citrine", "Peridot", "Turquoise", "Opal"]:
        return round(random.uniform(0.25, 1.5), 2)
    return None


def calculate_stone_value(stone, stone_cut, carat_weight):
    if not stone or not carat_weight:
        return 0
    if stone in ["Diamond", "Solitaire"]:
        low, high = (40000, 80000)
    elif stone in ["Ruby", "Emerald", "Sapphire"]:
        low, high = (15000, 35000)
    else:
        low, high = (500, 3000)

    cut_multiplier = 1.0
    if stone_cut in ["Round Brilliant", "Emerald Cut", "Marquise"]:
        cut_multiplier = 1.12
    return int(carat_weight * random.randint(low, high) * cut_multiplier)


def calculate_price(category_name, subcategory, material, weight, style, stone, stone_cut, carat_weight):
    if is_accessory(category_name):
        return random.randint(149, 1999)
    if is_watch(category_name):
        return random.randint(1499, 12999)
    if is_combo(category_name):
        component_total = random.randint(2500, 45000)
        return int(component_total * 0.9)
    if material in FASHION_PRICE_BANDS:
        low, high = FASHION_PRICE_BANDS[material]
        multiplier = 1.0
        if stone:
            multiplier += random.uniform(0.12, 0.35)
        if style in ["Statement", "Art Deco", "Personalized"]:
            multiplier += random.uniform(0.08, 0.2)
        return int(random.randint(low, high) * multiplier)

    rate = FINE_GOLD_RATES.get(material)
    if rate is None:
        return random.randint(999, 9999)

    varied_rate = rate * random.uniform(0.95, 1.05)
    metal_value = weight * varied_rate
    complex_styles = ["Antique", "Temple", "Kundan", "Polki", "Meenakari", "Nakshi", "Bridal", "Heritage"]
    making_percent = random.uniform(0.16, 0.25) if style in complex_styles else random.uniform(0.08, 0.16)
    making_charges = metal_value * making_percent
    stone_value = calculate_stone_value(stone, stone_cut, carat_weight)
    return int(round(metal_value + making_charges + stone_value, -2))


def price_range_for(price):
    for label, low, high in PRICE_RANGES:
        if low <= price <= high:
            return label
    return "Rs.15000+"


def generate_name(category_name, subcategory, attrs):
    material = attrs["material"]
    style = attrs["style"]
    stone = attrs["stone"]
    size = attrs["size_detail"]
    finish = attrs["finish"]
    chain_style = attrs["chain_style"]
    collection = attrs["collection"]
    enamel_color = attrs["enamel_color"]

    if is_accessory(category_name):
        template = random.choice([
            "{style} {material} {subcategory}",
            "Compact {subcategory} for Jewellery Care",
            "{material} {subcategory}, Travel Friendly",
        ])
        return template.format(style=style, material=material.title(), subcategory=subcategory)

    if is_watch(category_name):
        return f"{style} {subcategory} with {attrs['size_detail']} Case"

    if is_combo(category_name):
        return random.choice([
            f"{style} {subcategory} Gift Set",
            f"{collection or 'Festive'} {subcategory} with Premium Finish",
            f"{material} {subcategory} Bundle",
        ])

    if "Birthstone" in collection:
        month, birthstone = random.choice(list(BIRTHSTONES.items()))
        return f"{material} Birthstone {subcategory} - {month} ({birthstone})"

    if "Personalized" in collection:
        personal = random.choice(["Initial", "Name", "Date"])
        return f"Personalized {material} {subcategory} with {personal} Engraving"

    if is_western_category(category_name):
        western_piece = random.choice(WESTERN_NAME_STYLES.get(subcategory, [subcategory]))
        if "Chain" in western_piece or "Necklace" in western_piece or "Bracelet" in western_piece:
            chain_label = chain_style or random.choice(CHAIN_STYLES)
            core = f"{material} {chain_label} {western_piece}"
        elif stone:
            core = f"{material} {stone} {western_piece}, {finish}"
        else:
            core = f"{style} {material} {western_piece}, {finish}"
    else:
        if enamel_color != "None" and "Meenakari" in style:
            core = f"Adjustable Meenakari {subcategory}, {enamel_color} Enamel"
        elif stone:
            core = f"{style} {material} {subcategory} with {stone} Accent"
        else:
            core = f"{style} {material} {subcategory}, {finish}"

    if size:
        core = f"{core}, {size}"
    return core


def make_unique_name(name, used_names):
    while name in used_names or Product.objects.filter(name=name).exists():
        name = f"{name} {fake.bothify(text='??##').lower()}"
    used_names.add(name)
    return name


def generate_description(name, category_name, subcategory, attrs):
    parts = [
        f"{name} crafted for {attrs['occasion']} styling.",
        f"Material: {attrs['material']}.",
        f"Finish: {attrs['finish']}.",
        f"Size detail: {attrs['size_detail'] or 'standard fit'}.",
        f"Weight: {attrs['weight']}g estimated.",
    ]

    if attrs["stone"]:
        stone_line = f"Stone: {attrs['stone']}"
        if attrs["stone_cut"]:
            stone_line += f", {attrs['stone_cut']} cut"
        if attrs["carat_weight"]:
            stone_line += f", {attrs['carat_weight']}ct"
        parts.append(stone_line + ".")

    if attrs["chain_style"]:
        parts.append(f"Chain style: {attrs['chain_style']}.")
    if attrs["setting"]:
        parts.append(f"Setting: {attrs['setting']}.")
    if attrs["regional_style"]:
        parts.append(f"Regional inspiration: {attrs['regional_style']}.")
    if attrs["is_adjustable"]:
        parts.append("Adjustable - One Size Fits All where applicable.")
    if attrs["collection"]:
        parts.append(f"Collection: {attrs['collection']}.")

    parts.append(f"A realistic Aurum catalog piece for {attrs['who_for']} in {category_name} / {subcategory}.")
    return "\n".join(parts)


def generate_tags(category_name, subcategory, attrs):
    tags = [
        category_name,
        subcategory,
        attrs["material"],
        attrs["occasion"],
        attrs["who_for"],
        attrs["style"],
        attrs["finish"],
    ]
    for key in [
        "stone", "collection", "chain_style", "regional_style", "enamel_color",
        "setting", "stone_cut",
    ]:
        value = attrs.get(key)
        if value and value != "None":
            tags.append(value)
    if attrs["is_adjustable"]:
        tags.append("adjustable")
    return clean_tag_names(tags)


def clean_tag_names(tags):
    cleaned = []
    for tag in tags:
        tag = str(tag).strip().lower()
        if tag and tag not in cleaned:
            cleaned.append(tag)
    random.shuffle(cleaned)
    return cleaned[:10]


def build_product_counts():
    pairs = [
        (category_name, subcategory)
        for category_name, subcategories in CATEGORY_GROUPS.items()
        for subcategory in subcategories
    ]
    counts = {pair: MIN_PER_PAIR for pair in pairs}

    while sum(counts.values()) < TARGET_PRODUCT_COUNT:
        pair = random.choice(pairs)
        if counts[pair] < MAX_PER_PAIR:
            counts[pair] += 1

    return counts


def unique_slug_for_tag(tag_name):
    base_slug = slugify(tag_name)[:45] or fake.bothify(text="tag-####")
    slug = base_slug
    index = 2
    while Tag.objects.filter(slug=slug).exists():
        suffix = f"-{index}"
        slug = f"{base_slug[:60 - len(suffix)]}{suffix}"
        index += 1
    return slug


def unique_slug_for_product(name):
    base_slug = slugify(name)[:210] or fake.bothify(text="product-####")
    slug = f"{base_slug}-{fake.bothify(text='??##').lower()}"
    while Product.objects.filter(slug=slug).exists():
        slug = f"{base_slug[:210]}-{fake.bothify(text='??##').lower()}"
    return slug


def create_product_attrs(category_name, subcategory):
    western = is_western_category(category_name)
    styles = WESTERN_STYLES if western else INDIAN_STYLES
    material = choose_material(category_name, subcategory)
    stone = choose_stone(category_name, subcategory, material)
    stone_cut = random.choice(STONE_CUTS) if stone else ""
    carat_weight = choose_carat_weight(stone)
    occasion = random.choice(OCCASIONS)
    style = random.choice(styles)
    collection = choose_collection(category_name, subcategory, occasion, stone)

    if category_name == "Bridal Collection":
        occasion = "bridal"
        style = random.choice(["Bridal", "Kundan", "Polki", "Royal", "Heritage"])
    elif subcategory == "Temple":
        style = random.choice(["Temple", "Antique", "Nakshi", "Traditional"])
    elif collection == "Personalized":
        style = "Personalized"
    elif collection == "Birthstone Jewellery":
        style = "Birthstone"

    attrs = {
        "material": material,
        "purity": split_material(material)[0],
        "metal_color": split_material(material)[1],
        "occasion": occasion,
        "who_for": get_who_for(category_name, subcategory),
        "style": style,
        "finish": random.choice(FINISHES),
        "setting": random.choice(SETTINGS) if stone else "",
        "chain_style": random.choice(CHAIN_STYLES) if subcategory in ["Necklaces", "Bracelets", "Men's"] and western else "",
        "enamel_color": random.choice(ENAMEL_COLORS) if not western and random.random() < 0.25 else "None",
        "regional_style": random.choice(REGIONAL_STYLES) if not western and random.random() < 0.45 else "",
        "stone": stone,
        "stone_cut": stone_cut,
        "carat_weight": carat_weight,
        "weight": choose_weight(subcategory),
        "size_detail": choose_size_detail(subcategory),
        "is_adjustable": is_adjustable(subcategory, category_name),
        "collection": collection,
    }
    attrs["engraving_text"] = choose_engraving_text(collection)
    attrs["is_personalized"] = bool(attrs["engraving_text"])
    attrs["price"] = calculate_price(
        category_name,
        subcategory,
        material,
        attrs["weight"],
        attrs["style"],
        stone,
        stone_cut,
        carat_weight,
    )
    attrs["price_range"] = price_range_for(attrs["price"])
    return attrs


print("Creating categories and subcategories...")
category_objects = {}
subcategory_objects = {}

for category_index, category_name in enumerate(CATEGORY_DISPLAY_ORDER, start=1):
    category, _ = Category.objects.get_or_create(
        name=category_name,
        defaults={
            "slug": slugify(category_name),
            "description": f"{category_name} collection",
            "display_order": category_index,
        },
    )
    Category.objects.filter(pk=category.pk).update(display_order=category_index)
    category_objects[category_name] = category

    for subcategory_index, subcategory_name in enumerate(CATEGORY_GROUPS[category_name], start=1):
        subcategory, _ = Subcategory.objects.get_or_create(
            category=category,
            slug=slugify(subcategory_name),
            defaults={
                "name": subcategory_name,
                "description": f"{subcategory_name} in {category_name}",
                "display_order": subcategory_index,
                "is_new": (category_name, subcategory_name) in NEW_SUBCATEGORIES,
            },
        )
        Subcategory.objects.filter(pk=subcategory.pk).update(
            name=subcategory_name,
            display_order=subcategory_index,
            is_new=(category_name, subcategory_name) in NEW_SUBCATEGORIES,
        )
        subcategory_objects[(category_name, subcategory_name)] = subcategory

Category.objects.exclude(name__in=CATEGORY_DISPLAY_ORDER).update(is_active=False)
Category.objects.filter(name__in=CATEGORY_DISPLAY_ORDER).update(is_active=True)

for category_name, category in category_objects.items():
    Subcategory.objects.filter(category=category).exclude(
        name__in=CATEGORY_GROUPS[category_name]
    ).delete()


def seed_variant_example():
    """Create one small variation group without rebuilding the product catalog."""
    demo_slugs = [
        "variant-demo-aurora-ring-yellow-gold",
        "variant-demo-aurora-ring-rose-gold",
        "variant-demo-aurora-ring-white-gold",
    ]
    if Product.objects.filter(slug__in=demo_slugs).exists():
        print("Aurora Ring variation example already exists.")
        return

    base_product = Product.objects.filter(
        primary_subcategory__name__icontains="ring",
    ).first()
    if not base_product:
        print("No ring product exists to use as the variation example base.")
        return

    group_id = uuid.uuid5(uuid.NAMESPACE_URL, "aurum-aurora-ring-variants")
    excluded_fields = {
        "id", "name", "slug", "price", "stock", "metal_color",
        "variant_group", "variant_attributes",
    }
    shared_values = {
        field.name: getattr(base_product, field.name)
        for field in Product._meta.concrete_fields
        if field.name not in excluded_fields
    }
    categories = list(base_product.categories.all())
    subcategories = list(base_product.subcategories.all())
    tags = list(base_product.tags.all())

    examples = [
        ("Yellow Gold", demo_slugs[0], 0, 12),
        ("Rose Gold", demo_slugs[1], 1500, 8),
        ("White Gold", demo_slugs[2], 2500, 0),
    ]
    for metal_color, slug, price_delta, stock in examples:
        variant = Product.objects.create(
            **shared_values,
            name=f"Aurora Ring - {metal_color}",
            slug=slug,
            price=base_product.price + price_delta,
            stock=stock,
            metal_color=metal_color,
            variant_group=group_id,
            variant_attributes={"metal_color": metal_color},
        )
        variant.categories.set(categories)
        variant.subcategories.set(subcategories)
        variant.tags.set(tags)

    print("Created Aurora Ring metal variation example.")


if os.environ.get("AURUM_SEED_VARIANT_EXAMPLE_ONLY") == "1":
    seed_variant_example()
    raise SystemExit(0)

product_counts = build_product_counts()
used_names = set()
created_count = 0

print(f"Creating approximately {TARGET_PRODUCT_COUNT} jewellery products...")

for (category_name, subcategory), count in product_counts.items():
    category = category_objects[category_name]
    primary_subcategory = subcategory_objects[(category_name, subcategory)]

    for _ in range(count):
        attrs = create_product_attrs(category_name, subcategory)
        name = make_unique_name(generate_name(category_name, subcategory, attrs), used_names)

        product = Product.objects.create(
            name=name,
            slug=unique_slug_for_product(name),
            primary_category=category,
            primary_subcategory=primary_subcategory,
            material=attrs["material"],
            purity=attrs["purity"],
            metal_color=attrs["metal_color"],
            stone_type=attrs["stone"] or "",
            stone_cut=attrs["stone_cut"],
            carat_weight=attrs["carat_weight"],
            weight_grams=attrs["weight"],
            finish=attrs["finish"],
            setting=attrs["setting"],
            chain_style=attrs["chain_style"],
            collection=attrs["collection"],
            regional_style=attrs["regional_style"],
            enamel_color="" if attrs["enamel_color"] == "None" else attrs["enamel_color"],
            size_detail=attrs["size_detail"],
            is_adjustable=attrs["is_adjustable"],
            is_personalized=attrs["is_personalized"],
            engraving_text=attrs["engraving_text"],
            occasion=attrs["occasion"],
            who_for=attrs["who_for"],
            price_range=attrs["price_range"],
            description=generate_description(name, category_name, subcategory, attrs),
            price=attrs["price"],
            stock=random.randint(4, 150),
            is_new=random.choice([True, False, False, False]),
        )
        product.categories.add(category)
        product.subcategories.add(primary_subcategory)

        for tag_name in generate_tags(category_name, subcategory, attrs):
            tag, _ = Tag.objects.get_or_create(
                name=tag_name,
                defaults={"slug": unique_slug_for_tag(tag_name)},
            )
            product.tags.add(tag)

        created_count += 1

print(f"Done. Created {created_count} products.")
print(f"Created or reused {Category.objects.count()} categories.")
print(f"Created or reused {Tag.objects.count()} tags.")
