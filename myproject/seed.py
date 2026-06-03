import os
import django
import urllib.request
import tempfile
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from shop.models import Product
from django.core.files import File

products_data = [
    # RINGS
    ("Éclat Sapphire Ring", 3200, "https://source.unsplash.com/600x600/?sapphire-ring,jewelry&sig=1"),
    ("Lumière Diamond Ring", 4800, "https://source.unsplash.com/600x600/?diamond-ring,jewelry&sig=2"),
    ("Céleste Ruby Ring", 5200, "https://source.unsplash.com/600x600/?ruby-ring,jewelry&sig=3"),
    ("Imperial Emerald Ring", 6800, "https://source.unsplash.com/600x600/?emerald-ring,jewelry&sig=4"),
    ("Eternal Diamond Solitaire", 9999, "https://source.unsplash.com/600x600/?solitaire-diamond-ring&sig=5"),
    ("Rose Gold Twisted Band", 2400, "https://source.unsplash.com/600x600/?rose-gold-ring&sig=6"),
    ("Blanc Diamond Eternity Band", 7200, "https://source.unsplash.com/600x600/?diamond-eternity-band&sig=7"),
    ("Noir Onyx Ring", 3800, "https://source.unsplash.com/600x600/?black-onyx-ring&sig=8"),

    # EARRINGS
    ("Rivière Diamond Earrings", 5600, "https://source.unsplash.com/600x600/?diamond-earrings&sig=9"),
    ("Céleste Sapphire Studs", 3200, "https://source.unsplash.com/600x600/?sapphire-earrings&sig=10"),
    ("Pearl Drop Earrings", 1800, "https://source.unsplash.com/600x600/?pearl-earrings&sig=11"),
    ("Noir Black Diamond Earrings", 7800, "https://source.unsplash.com/600x600/?black-earrings,jewelry&sig=12"),
    ("Ruby Chandelier Earrings", 4500, "https://source.unsplash.com/600x600/?ruby-earrings&sig=13"),
    ("Geometric Gold Earrings", 2200, "https://source.unsplash.com/600x600/?gold-earrings&sig=14"),
    ("Lumière Opal Earrings", 2800, "https://source.unsplash.com/600x600/?opal-earrings&sig=15"),
    ("Divine Emerald Ear Cuffs", 3600, "https://source.unsplash.com/600x600/?emerald-earrings&sig=16"),

    # NECKLACES
    ("Lumière Pearl Strand", 3800, "https://source.unsplash.com/600x600/?pearl-necklace&sig=17"),
    ("Diamond Tennis Necklace", 12000, "https://source.unsplash.com/600x600/?diamond-necklace&sig=18"),
    ("Céleste Sapphire Necklace", 5600, "https://source.unsplash.com/600x600/?sapphire-necklace&sig=19"),
    ("Gold Lariat Necklace", 3200, "https://source.unsplash.com/600x600/?gold-necklace&sig=20"),
    ("Heart Diamond Necklace", 4200, "https://source.unsplash.com/600x600/?heart-necklace,jewelry&sig=21"),
    ("Vintage Sapphire Pendant Necklace", 6800, "https://source.unsplash.com/600x600/?vintage-pendant-necklace&sig=22"),
    ("Rose Gold Infinity Necklace", 2800, "https://source.unsplash.com/600x600/?rose-gold-necklace&sig=23"),

    # BRACELETS
    ("Diamond Tennis Bracelet", 15000, "https://source.unsplash.com/600x600/?diamond-bracelet&sig=24"),
    ("Jardin Pearl Bracelet", 2100, "https://source.unsplash.com/600x600/?pearl-bracelet&sig=25"),
    ("Aurum Gold Bangle", 2800, "https://source.unsplash.com/600x600/?gold-bangle&sig=26"),
    ("Imperial Diamond Cuff", 9800, "https://source.unsplash.com/600x600/?diamond-cuff-bracelet&sig=27"),
    ("Divine Ruby Bangle", 4500, "https://source.unsplash.com/600x600/?ruby-bracelet&sig=28"),
    ("Eternal Gold Charm Bracelet", 3200, "https://source.unsplash.com/600x600/?gold-charm-bracelet&sig=29"),
    ("Sapphire Line Bracelet", 5600, "https://source.unsplash.com/600x600/?sapphire-bracelet&sig=30"),

    # PENDANTS
    ("Éclat Diamond Pendant", 4800, "https://source.unsplash.com/600x600/?diamond-pendant&sig=31"),
    ("Céleste Star Pendant", 2200, "https://source.unsplash.com/600x600/?star-pendant,jewelry&sig=32"),
    ("Rivière Diamond Pendant", 5600, "https://source.unsplash.com/600x600/?luxury-pendant&sig=33"),
    ("Moon Opal Pendant", 1800, "https://source.unsplash.com/600x600/?opal-pendant&sig=34"),
    ("Infinity Diamond Pendant", 3800, "https://source.unsplash.com/600x600/?infinity-necklace&sig=35"),
    ("Rose Gold Feather Pendant", 2400, "https://source.unsplash.com/600x600/?feather-pendant&sig=36"),
    ("Heritage Cufflinks", 720, "https://source.unsplash.com/600x600/?gold-cufflinks&sig=37"),

    # HANDBAGS
    ("Milano Suede Clutch", 890, "https://source.unsplash.com/600x600/?suede-clutch-bag&sig=38"),
    ("Séville Leather Tote", 1290, "https://source.unsplash.com/600x600/?leather-tote-bag&sig=39"),
    ("Voyage Weekender Bag", 2450, "https://source.unsplash.com/600x600/?weekender-bag&sig=40"),
    ("Noir Quilted Chain Bag", 3800, "https://source.unsplash.com/600x600/?quilted-chain-bag&sig=41"),
    ("Riviera Mini Bag", 1650, "https://source.unsplash.com/600x600/?mini-handbag&sig=42"),
    ("Maison Shoulder Bag", 2100, "https://source.unsplash.com/600x600/?shoulder-bag&sig=43"),
    ("Céleste Evening Clutch", 980, "https://source.unsplash.com/600x600/?evening-clutch&sig=44"),
    ("Imperial Leather Satchel", 3200, "https://source.unsplash.com/600x600/?leather-satchel&sig=45"),
    ("Lumière Bucket Bag", 1750, "https://source.unsplash.com/600x600/?bucket-bag&sig=46"),
    ("Aurum Crossbody Bag", 1200, "https://source.unsplash.com/600x600/?crossbody-bag&sig=47"),
    ("Blanc Structured Handbag", 2800, "https://source.unsplash.com/600x600/?structured-handbag&sig=48"),
    ("Soleil Woven Bag", 1450, "https://source.unsplash.com/600x600/?woven-bag&sig=49"),

    # TIMEPIECES
    ("Prestige 38 Moonphase", 12500, "https://source.unsplash.com/600x600/?luxury-watch&sig=50"),
    ("Tourbillon Classique", 18900, "https://source.unsplash.com/600x600/?mechanical-watch&sig=51"),
    ("Calendrier Perpétuel", 9800, "https://source.unsplash.com/600x600/?classic-watch&sig=52"),
    ("Lumière Dress Watch", 4500, "https://source.unsplash.com/600x600/?dress-watch&sig=53"),
    ("Noir Chronograph", 7800, "https://source.unsplash.com/600x600/?chronograph-watch&sig=54"),
    ("Céleste Ladies Watch", 5600, "https://source.unsplash.com/600x600/?ladies-watch&sig=55"),
    ("Imperial GMT Watch", 11200, "https://source.unsplash.com/600x600/?gmt-watch&sig=56"),
    ("Rivière Skeleton Watch", 15000, "https://source.unsplash.com/600x600/?skeleton-watch&sig=57"),
    ("Aurum Gold Watch", 8900, "https://source.unsplash.com/600x600/?gold-watch&sig=58"),
    ("Soleil Automatic Watch", 6200, "https://source.unsplash.com/600x600/?automatic-watch&sig=59"),
    ("Éclat Rose Gold Watch", 7200, "https://source.unsplash.com/600x600/?rose-gold-watch&sig=60"),
    ("Divine Platinum Watch", 22000, "https://source.unsplash.com/600x600/?silver-luxury-watch&sig=61"),

    # ACCESSORIES
    ("Ascot Silk Scarf", 380, "https://source.unsplash.com/600x600/?silk-scarf&sig=62"),
    ("Heritage Leather Belt", 450, "https://source.unsplash.com/600x600/?leather-belt&sig=63"),
    ("Maison Silk Tie", 280, "https://source.unsplash.com/600x600/?silk-tie&sig=64"),
    ("Lumière Sunglasses", 620, "https://source.unsplash.com/600x600/?luxury-sunglasses&sig=65"),
    ("Imperial Leather Wallet", 390, "https://source.unsplash.com/600x600/?leather-wallet&sig=66"),
    ("Noir Leather Gloves", 520, "https://source.unsplash.com/600x600/?leather-gloves&sig=67"),
    ("Céleste Hair Pins Set", 180, "https://source.unsplash.com/600x600/?hair-accessories&sig=68"),
    ("Rivière Brooch", 650, "https://source.unsplash.com/600x600/?brooch-jewelry&sig=69"),
    ("Aurum Leather Keychain", 120, "https://source.unsplash.com/600x600/?leather-keychain&sig=70"),
    ("Soleil Silk Pocket Square", 160, "https://source.unsplash.com/600x600/?pocket-square&sig=71"),
]

def download_image(url):
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            tmp.write(response.read())
        tmp.flush()
        return tmp
    except Exception as e:
        print(f"    ⚠️  Could not download image: {e}")
        return None

print(f"Creating {len(products_data)} products...\n")

for name, price, image_url in products_data:
    print(f"  Adding: {name}")
    product = Product(name=name, price=price)

    tmp = download_image(image_url)
    if tmp:
        filename = name.lower().replace(' ', '_').replace('é', 'e').replace('è', 'e').replace('ê', 'e').replace('î', 'i').replace('ô', 'o').replace('û', 'u') + '.jpg'
        with open(tmp.name, 'rb') as f:
            product.image.save(filename, File(f), save=False)

    product.save()

print(f"\n✅ Done! {len(products_data)} products created with images.")