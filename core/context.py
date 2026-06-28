from django.db.models import F

from .models import Product


def company_context(request):
    membership = None
    if request.user.is_authenticated:
        membership = request.user.memberships.filter(active=True).select_related("company").first()
    return {"membership": membership, "company": membership.company if membership else None}


def inventory_warning_context(request):
    membership = None
    if request.user.is_authenticated:
        membership = request.user.memberships.filter(active=True).select_related("company").first()
    if not membership:
        return {
            "inventory_warning_count": 0,
            "inventory_warning_critical_count": 0,
            "inventory_warning_products": [],
        }

    warning_products = Product.objects.filter(
        company=membership.company,
        active=True,
        track_inventory=True,
        stock_quantity__lte=F("low_stock_threshold"),
    ).order_by("stock_quantity", "name")
    return {
        "inventory_warning_count": warning_products.count(),
        "inventory_warning_critical_count": warning_products.filter(stock_quantity__lt=0).count(),
        "inventory_warning_products": list(warning_products[:5]),
    }
