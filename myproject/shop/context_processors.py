from .models import Category, MetalRate


MEGA_MENU_SUBCATEGORY_LIMIT = 40


def mega_menu(request):
    categories = (
        Category.objects.filter(is_active=True)
        .prefetch_related("subcategories")
        .order_by("display_order", "name")
    )

    menu_categories = []
    for category in categories:
        subcategories = list(category.subcategories.all())
        menu_categories.append(
            {
                "category": category,
                "visible_subcategories": subcategories[:MEGA_MENU_SUBCATEGORY_LIMIT],
                "has_more": len(subcategories) > MEGA_MENU_SUBCATEGORY_LIMIT,
                "subcategory_count": len(subcategories),
            }
        )

    return {
        "mega_menu_categories": menu_categories,
        "mega_menu_subcategory_limit": MEGA_MENU_SUBCATEGORY_LIMIT,
    }


def metal_rate_ticker(request):
    """Expose the latest stored display rates to the shared storefront chrome."""
    rate_specs = (
        ("Gold 24K", MetalRate.GOLD, "24K"),
        ("Gold 22K", MetalRate.GOLD, "22K"),
        ("Gold 18K", MetalRate.GOLD, "18K"),
        ("Silver", MetalRate.SILVER, "925"),
        ("Platinum", MetalRate.PLATINUM, "950"),
    )
    rates = []

    for label, metal, purity in rate_specs:
        rate = MetalRate.objects.get_latest(metal, purity)
        if rate is not None:
            rates.append({"label": label, "rate": rate})

    # A partial set could mislead customers, so only show a complete ticker.
    if len(rates) != len(rate_specs):
        return {"metal_rate_ticker": []}

    return {
        "metal_rate_ticker": rates,
        "metal_rate_ticker_updated_at": max(
            item["rate"].fetched_at for item in rates
        ),
    }
