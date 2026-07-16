from .models import Category


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
