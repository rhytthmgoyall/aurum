import os
import django
import urllib.request
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from shop.models import Product, Category
from django.core.files import File


BASE_DIR = Path(__file__).resolve().parent
PRODUCT_MEDIA_DIR = BASE_DIR / "media" / "products"


categories_data = {
    "Rings": {
        "slug": "rings",
        "description": "Luxury rings crafted with diamonds, sapphires, rubies, emeralds, and fine gold.",
    },
    "Earrings": {
        "slug": "earrings",
        "description": "Elegant earrings including studs, drops, chandeliers, cuffs, and gemstone designs.",
    },
    "Necklaces": {
        "slug": "necklaces",
        "description": "Premium necklaces, pearl strands, diamond pieces, and statement pendants.",
    },
    "Bracelets": {
        "slug": "bracelets",
        "description": "Fine bracelets, bangles, cuffs, tennis bracelets, and charm pieces.",
    },
    "Pendants": {
        "slug": "pendants",
        "description": "Luxury pendants and refined small accessories with elegant detailing.",
    },
    "Handbags": {
        "slug": "handbags",
        "description": "Designer handbags, totes, clutches, mini bags, satchels, and leather pieces.",
    },
    "Timepieces": {
        "slug": "timepieces",
        "description": "Luxury watches, automatic timepieces, chronographs, GMT watches, and dress watches.",
    },
    "Accessories": {
        "slug": "accessories",
        "description": "Premium scarves, belts, sunglasses, wallets, gloves, ties, and small accessories.",
    },
}

products_data = [
    # RINGS
    ("Éclat Sapphire Ring", 3200, "Rings", "https://source.unsplash.com/600x600/?sapphire-ring,jewelry&sig=1"),
    ("Lumière Diamond Ring", 4800, "Rings", "https://source.unsplash.com/600x600/?diamond-ring,jewelry&sig=2"),
    ("Céleste Ruby Ring", 5200, "Rings", "https://source.unsplash.com/600x600/?ruby-ring,jewelry&sig=3"),
    ("Imperial Emerald Ring", 6800, "Rings", "https://source.unsplash.com/600x600/?emerald-ring,jewelry&sig=4"),
    ("Eternal Diamond Solitaire", 9999, "Rings", "https://source.unsplash.com/600x600/?solitaire-diamond-ring&sig=5"),
    ("Rose Gold Twisted Band", 2400, "Rings", "https://source.unsplash.com/600x600/?rose-gold-ring&sig=6"),
    ("Blanc Diamond Eternity Band", 7200, "Rings", "https://source.unsplash.com/600x600/?diamond-eternity-band&sig=7"),
    ("Noir Onyx Ring", 3800, "Rings", "https://source.unsplash.com/600x600/?black-onyx-ring&sig=8"),
    ("Royal Tanzanite Ring", 5900, "Rings", "https://source.unsplash.com/600x600/?tanzanite-ring&sig=9"),
    ("Vintage Diamond Halo Ring", 7200, "Rings", "https://source.unsplash.com/600x600/?diamond-halo-ring&sig=10"),
    ("Imperial Topaz Ring", 4300, "Rings", "https://source.unsplash.com/600x600/?topaz-ring&sig=11"),
    ("Celestial Moonstone Ring", 2800, "Rings", "https://source.unsplash.com/600x600/?moonstone-ring&sig=12"),
    ("Aurora Pink Sapphire Ring", 6100, "Rings", "https://source.unsplash.com/600x600/?pink-sapphire-ring&sig=13"),
    ("Signature Platinum Band", 3900, "Rings", "https://source.unsplash.com/600x600/?platinum-ring&sig=14"),
    ("Golden Heritage Ring", 4600, "Rings", "https://source.unsplash.com/600x600/?gold-ring&sig=15"),

    # EARRINGS
    ("Rivière Diamond Earrings", 5600, "Earrings", "https://source.unsplash.com/600x600/?diamond-earrings&sig=16"),
    ("Céleste Sapphire Studs", 3200, "Earrings", "https://source.unsplash.com/600x600/?sapphire-earrings&sig=17"),
    ("Pearl Drop Earrings", 1800, "Earrings", "https://source.unsplash.com/600x600/?pearl-earrings&sig=18"),
    ("Noir Black Diamond Earrings", 7800, "Earrings", "https://source.unsplash.com/600x600/?black-diamond-earrings&sig=19"),
    ("Ruby Chandelier Earrings", 4500, "Earrings", "https://source.unsplash.com/600x600/?ruby-earrings&sig=20"),
    ("Geometric Gold Earrings", 2200, "Earrings", "https://source.unsplash.com/600x600/?gold-earrings&sig=21"),
    ("Lumière Opal Earrings", 2800, "Earrings", "https://source.unsplash.com/600x600/?opal-earrings&sig=22"),
    ("Divine Emerald Ear Cuffs", 3600, "Earrings", "https://source.unsplash.com/600x600/?emerald-earrings&sig=23"),
    ("Diamond Cascade Earrings", 6200, "Earrings", "https://source.unsplash.com/600x600/?diamond-drop-earrings&sig=24"),
    ("Pearl Blossom Earrings", 2200, "Earrings", "https://source.unsplash.com/600x600/?pearl-stud-earrings&sig=25"),
    ("Royal Sapphire Drops", 4900, "Earrings", "https://source.unsplash.com/600x600/?sapphire-drop-earrings&sig=26"),
    ("Golden Hoop Luxe", 1800, "Earrings", "https://source.unsplash.com/600x600/?gold-hoop-earrings&sig=27"),
    ("Imperial Ruby Studs", 5300, "Earrings", "https://source.unsplash.com/600x600/?ruby-stud-earrings&sig=28"),

    # NECKLACES
    ("Lumière Pearl Strand", 3800, "Necklaces", "https://source.unsplash.com/600x600/?pearl-necklace&sig=29"),
    ("Diamond Tennis Necklace", 12000, "Necklaces", "https://source.unsplash.com/600x600/?diamond-necklace&sig=30"),
    ("Céleste Sapphire Necklace", 5600, "Necklaces", "https://source.unsplash.com/600x600/?sapphire-necklace&sig=31"),
    ("Gold Lariat Necklace", 3200, "Necklaces", "https://source.unsplash.com/600x600/?gold-necklace&sig=32"),
    ("Heart Diamond Necklace", 4200, "Necklaces", "https://source.unsplash.com/600x600/?heart-necklace,jewelry&sig=33"),
    ("Vintage Sapphire Pendant Necklace", 6800, "Necklaces", "https://source.unsplash.com/600x600/?vintage-pendant-necklace&sig=34"),
    ("Rose Gold Infinity Necklace", 2800, "Necklaces", "https://source.unsplash.com/600x600/?rose-gold-necklace&sig=35"),
    ("Emerald Collar Necklace", 8900, "Necklaces", "https://source.unsplash.com/600x600/?emerald-necklace&sig=36"),
    ("Royal Ruby Necklace", 7600, "Necklaces", "https://source.unsplash.com/600x600/?ruby-necklace&sig=37"),
    ("Noir Diamond Choker", 9400, "Necklaces", "https://source.unsplash.com/600x600/?diamond-choker&sig=38"),
    ("Celestial Moon Necklace", 2600, "Necklaces", "https://source.unsplash.com/600x600/?moon-necklace&sig=39"),
    ("Imperial Gold Chain", 5100, "Necklaces", "https://source.unsplash.com/600x600/?luxury-gold-chain&sig=40"),

    # BRACELETS
    ("Diamond Tennis Bracelet", 15000, "Bracelets", "https://source.unsplash.com/600x600/?diamond-bracelet&sig=41"),
    ("Jardin Pearl Bracelet", 2100, "Bracelets", "https://source.unsplash.com/600x600/?pearl-bracelet&sig=42"),
    ("Aurum Gold Bangle", 2800, "Bracelets", "https://source.unsplash.com/600x600/?gold-bangle&sig=43"),
    ("Imperial Diamond Cuff", 9800, "Bracelets", "https://source.unsplash.com/600x600/?diamond-cuff-bracelet&sig=44"),
    ("Divine Ruby Bangle", 4500, "Bracelets", "https://source.unsplash.com/600x600/?ruby-bracelet&sig=45"),
    ("Eternal Gold Charm Bracelet", 3200, "Bracelets", "https://source.unsplash.com/600x600/?gold-charm-bracelet&sig=46"),
    ("Sapphire Line Bracelet", 5600, "Bracelets", "https://source.unsplash.com/600x600/?sapphire-bracelet&sig=47"),
    ("Emerald Tennis Bracelet", 7200, "Bracelets", "https://source.unsplash.com/600x600/?emerald-bracelet&sig=48"),
    ("Noir Onyx Bracelet", 3400, "Bracelets", "https://source.unsplash.com/600x600/?onyx-bracelet&sig=49"),
    ("Rose Gold Link Bracelet", 2900, "Bracelets", "https://source.unsplash.com/600x600/?rose-gold-bracelet&sig=50"),
    ("Pearl Chain Bracelet", 1900, "Bracelets", "https://source.unsplash.com/600x600/?pearl-chain-bracelet&sig=51"),
    ("Imperial Platinum Cuff", 10500, "Bracelets", "https://source.unsplash.com/600x600/?platinum-cuff-bracelet&sig=52"),

    # PENDANTS
    ("Éclat Diamond Pendant", 4800, "Pendants", "https://source.unsplash.com/600x600/?diamond-pendant&sig=53"),
    ("Céleste Star Pendant", 2200, "Pendants", "https://source.unsplash.com/600x600/?star-pendant,jewelry&sig=54"),
    ("Rivière Diamond Pendant", 5600, "Pendants", "https://source.unsplash.com/600x600/?luxury-pendant&sig=55"),
    ("Moon Opal Pendant", 1800, "Pendants", "https://source.unsplash.com/600x600/?opal-pendant&sig=56"),
    ("Infinity Diamond Pendant", 3800, "Pendants", "https://source.unsplash.com/600x600/?infinity-necklace&sig=57"),
    ("Rose Gold Feather Pendant", 2400, "Pendants", "https://source.unsplash.com/600x600/?feather-pendant&sig=58"),
    ("Royal Emerald Pendant", 5200, "Pendants", "https://source.unsplash.com/600x600/?emerald-pendant&sig=59"),
    ("Ruby Heart Pendant", 4300, "Pendants", "https://source.unsplash.com/600x600/?ruby-heart-pendant&sig=60"),
    ("Pearl Drop Pendant", 2100, "Pendants", "https://source.unsplash.com/600x600/?pearl-pendant&sig=61"),
    ("Noir Onyx Pendant", 2700, "Pendants", "https://source.unsplash.com/600x600/?onyx-pendant&sig=62"),

    # HANDBAGS
    ("Milano Suede Clutch", 890, "Handbags", "https://source.unsplash.com/600x600/?suede-clutch-bag&sig=63"),
    ("Séville Leather Tote", 1290, "Handbags", "https://source.unsplash.com/600x600/?leather-tote-bag&sig=64"),
    ("Voyage Weekender Bag", 2450, "Handbags", "https://source.unsplash.com/600x600/?weekender-bag&sig=65"),
    ("Noir Quilted Chain Bag", 3800, "Handbags", "https://source.unsplash.com/600x600/?quilted-chain-bag&sig=66"),
    ("Riviera Mini Bag", 1650, "Handbags", "https://source.unsplash.com/600x600/?mini-handbag&sig=67"),
    ("Maison Shoulder Bag", 2100, "Handbags", "https://source.unsplash.com/600x600/?shoulder-bag&sig=68"),
    ("Céleste Evening Clutch", 980, "Handbags", "https://source.unsplash.com/600x600/?evening-clutch&sig=69"),
    ("Imperial Leather Satchel", 3200, "Handbags", "https://source.unsplash.com/600x600/?leather-satchel&sig=70"),
    ("Lumière Bucket Bag", 1750, "Handbags", "https://source.unsplash.com/600x600/?bucket-bag&sig=71"),
    ("Aurum Crossbody Bag", 1200, "Handbags", "https://source.unsplash.com/600x600/?crossbody-bag&sig=72"),
    ("Blanc Structured Handbag", 2800, "Handbags", "https://source.unsplash.com/600x600/?structured-handbag&sig=73"),
    ("Soleil Woven Bag", 1450, "Handbags", "https://source.unsplash.com/600x600/?woven-bag&sig=74"),
    ("Venice Leather Tote", 1900, "Handbags", "https://source.unsplash.com/600x600/?designer-leather-tote&sig=75"),
    ("Paris Evening Clutch", 1450, "Handbags", "https://source.unsplash.com/600x600/?luxury-evening-clutch&sig=76"),
    ("Imperial Croc Bag", 4200, "Handbags", "https://source.unsplash.com/600x600/?croc-leather-bag&sig=77"),
    ("Soleil Travel Tote", 2100, "Handbags", "https://source.unsplash.com/600x600/?travel-tote-bag&sig=78"),
    ("Noir Luxe Satchel", 3500, "Handbags", "https://source.unsplash.com/600x600/?black-leather-satchel&sig=79"),
    ("Milano Structured Bag", 2700, "Handbags", "https://source.unsplash.com/600x600/?luxury-structured-bag&sig=80"),

    # TIMEPIECES
    ("Prestige 38 Moonphase", 12500, "Timepieces", "https://source.unsplash.com/600x600/?luxury-watch&sig=81"),
    ("Tourbillon Classique", 18900, "Timepieces", "https://source.unsplash.com/600x600/?mechanical-watch&sig=82"),
    ("Calendrier Perpétuel", 9800, "Timepieces", "https://source.unsplash.com/600x600/?classic-watch&sig=83"),
    ("Lumière Dress Watch", 4500, "Timepieces", "https://source.unsplash.com/600x600/?dress-watch&sig=84"),
    ("Noir Chronograph", 7800, "Timepieces", "https://source.unsplash.com/600x600/?chronograph-watch&sig=85"),
    ("Céleste Ladies Watch", 5600, "Timepieces", "https://source.unsplash.com/600x600/?ladies-watch&sig=86"),
    ("Imperial GMT Watch", 11200, "Timepieces", "https://source.unsplash.com/600x600/?gmt-watch&sig=87"),
    ("Rivière Skeleton Watch", 15000, "Timepieces", "https://source.unsplash.com/600x600/?skeleton-watch&sig=88"),
    ("Aurum Gold Watch", 8900, "Timepieces", "https://source.unsplash.com/600x600/?gold-watch&sig=89"),
    ("Soleil Automatic Watch", 6200, "Timepieces", "https://source.unsplash.com/600x600/?automatic-watch&sig=90"),
    ("Éclat Rose Gold Watch", 7200, "Timepieces", "https://source.unsplash.com/600x600/?rose-gold-watch&sig=91"),
    ("Divine Platinum Watch", 22000, "Timepieces", "https://source.unsplash.com/600x600/?silver-luxury-watch&sig=92"),
    ("Prestige Chronometer", 11500, "Timepieces", "https://source.unsplash.com/600x600/?luxury-chronometer&sig=93"),
    ("Royal GMT Master", 14200, "Timepieces", "https://source.unsplash.com/600x600/?gmt-luxury-watch&sig=94"),
    ("Heritage Automatic", 5900, "Timepieces", "https://source.unsplash.com/600x600/?heritage-automatic-watch&sig=95"),
    ("Diamond Bezel Watch", 13800, "Timepieces", "https://source.unsplash.com/600x600/?diamond-bezel-watch&sig=96"),
    ("Noir Moonphase", 9200, "Timepieces", "https://source.unsplash.com/600x600/?moonphase-watch&sig=97"),
    ("Classic Leather Chronograph", 4800, "Timepieces", "https://source.unsplash.com/600x600/?leather-chronograph-watch&sig=98"),

    # ACCESSORIES
    ("Ascot Silk Scarf", 380, "Accessories", "https://source.unsplash.com/600x600/?silk-scarf&sig=99"),
    ("Heritage Leather Belt", 450, "Accessories", "https://source.unsplash.com/600x600/?leather-belt&sig=100"),
    ("Maison Silk Tie", 280, "Accessories", "https://source.unsplash.com/600x600/?silk-tie&sig=101"),
    ("Lumière Sunglasses", 620, "Accessories", "https://source.unsplash.com/600x600/?luxury-sunglasses&sig=102"),
    ("Imperial Leather Wallet", 390, "Accessories", "https://source.unsplash.com/600x600/?leather-wallet&sig=103"),
    ("Noir Leather Gloves", 520, "Accessories", "https://source.unsplash.com/600x600/?leather-gloves&sig=104"),
    ("Céleste Hair Pins Set", 180, "Accessories", "https://source.unsplash.com/600x600/?hair-accessories&sig=105"),
    ("Rivière Brooch", 650, "Accessories", "https://source.unsplash.com/600x600/?brooch-jewelry&sig=106"),
    ("Aurum Leather Keychain", 120, "Accessories", "https://source.unsplash.com/600x600/?leather-keychain&sig=107"),
    ("Soleil Silk Pocket Square", 160, "Accessories", "https://source.unsplash.com/600x600/?pocket-square&sig=108"),
    ("Golden Cufflinks", 720, "Accessories", "https://source.unsplash.com/600x600/?gold-cufflinks&sig=109"),
    ("Pearl Hair Comb", 310, "Accessories", "https://source.unsplash.com/600x600/?pearl-hair-comb&sig=110"),
    ("Noir Luxury Card Holder", 250, "Accessories", "https://source.unsplash.com/600x600/?leather-card-holder&sig=111"),
]

def download_image(url):
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req) as response:
            tmp.write(response.read())

        tmp.flush()
        return tmp

    except Exception as e:
        print(f"⚠️ Could not download image: {e}")
        return None


def clean_filename(name):
    return (
        name.lower()
        .replace(" ", "_")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("î", "i")
        .replace("ô", "o")
        .replace("û", "u")
        + ".jpg"
    )


def clean_png_filename(name):
    return clean_filename(name).removesuffix(".jpg") + ".png"


print("Creating categories...\n")

category_objects = {}

for category_name, data in categories_data.items():
    category, created = Category.objects.get_or_create(
        name=category_name,
        defaults={
            "slug": data["slug"],
            "description": data["description"],
        },
    )

    category_objects[category_name] = category

    if created:
        print(f"  ✅ Created category: {category_name}")
    else:
        print(f"  ℹ️ Category already exists: {category_name}")


print(f"\nCreating {len(products_data)} products...\n")

Product.objects.all().delete()

for name, price, category_name, image_url in products_data:
    print(f"  Adding: {name}")

    category = category_objects[category_name]

    product = Product(
        name=name,
        price=price,
        category=category,
    )

    local_png = PRODUCT_MEDIA_DIR / clean_png_filename(name)

    if local_png.exists():
        with open(local_png, "rb") as f:
            product.image.save(local_png.name, File(f), save=False)
    else:
        tmp = download_image(image_url)

    if not local_png.exists() and tmp:
        filename = clean_filename(name)
        with open(tmp.name, "rb") as f:
            product.image.save(filename, File(f), save=False)

    product.save()

print("\n✅ Done! Products created with categories.")
