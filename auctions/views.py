from urllib.parse import urlsplit

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_safe

from .comparison import current_comparison
from .forms import BoundsForm, LotFilter
from .models import AuctionLot
from .queries import COURT_SEARCH, MAP_LIMIT, SNAPSHOT_DATE, home_categories, map_lots, page_lots


def serialize_pin(lot):
    if lot.location is None:
        return None
    return {
        "id": lot.public_id, "name": lot.name,
        "longitude": lot.location.x, "latitude": lot.location.y,
        "price_label": lot.price_label, "price_won": lot.price,
        "display_price": lot.display_price,
        "url": reverse("auctions:detail", args=[lot.public_id]),
    }


def pins_for(lots):
    return [pin for lot in lots if (pin := serialize_pin(lot)) is not None]


@require_safe
def home(request):
    upcoming = map_lots({"kind": "upcoming"})
    sold = map_lots({"kind": "sold"})
    sold_preview = list(sold[:8])
    photos = [f"auctions/home-example-{index}.webp" for index in range(1, 5)]
    round_, single = current_comparison(request)
    return render(request, "auctions/home.html", {
        "filter": LotFilter(), "categories": home_categories(upcoming, sold),
        "upcoming": zip(upcoming[:8], photos * 2), "sold": zip(sold_preview, photos[2:] + photos * 2),
        "sold_title": "낙찰 사례" if any(lot.is_demo for lot in sold_preview) else "실제 낙찰 사례",
        "snapshot": SNAPSHOT_DATE, "active": "home",
        "current_round": round_, "single_lot": single,
    })


@require_safe
def listing_map(request):
    sold_view = request.GET.get("kind") == "sold"
    sale_dates = AuctionLot.objects.filter(
        bid__isnull=False, sale_date__isnull=False,
    ).order_by("-sale_date").values_list("sale_date", flat=True).distinct() if sold_view else ()
    form = LotFilter(request.GET, sale_dates=sale_dates)
    valid = form.is_valid()
    lots, truncated = page_lots(map_lots(form.cleaned_data)) if valid else ([], False)
    return render(request, "auctions/map.html", {
        "filter": form, "lots": lots, "pins": pins_for(lots), "truncated": truncated,
        "return_to": request.get_full_path(), "snapshot": SNAPSHOT_DATE, "active": "map",
        "kakao_key": settings.KAKAO_MAP_JS_KEY, "sold_view": sold_view,
    }, status=200 if valid else 400)


@require_safe
def map_api(request):
    filters, bounds = LotFilter(request.GET), BoundsForm(request.GET)
    if not (filters.is_valid() & bounds.is_valid()):
        return JsonResponse({"errors": filters.errors.get_json_data() | bounds.errors.get_json_data()}, status=400)
    lots, truncated = page_lots(map_lots(filters.cleaned_data, bbox=bounds.cleaned_data["bbox"]))
    return JsonResponse({
        "lots": pins_for(lots), "limit": MAP_LIMIT, "truncated": truncated,
        "list_html": render_to_string("auctions/_map_rows.html", {"lots": lots}, request=request),
    })


def safe_return(request):
    target = request.GET.get("return", "")
    if target.startswith("/") and url_has_allowed_host_and_scheme(target, allowed_hosts=set()):
        if urlsplit(target).path == reverse("auctions:map"):
            return target
    return reverse("auctions:map")


@require_safe
def lot_detail(request, public_id):
    lot = AuctionLot.objects.prefetch_related("comparable_sales", "events").filter(public_id=public_id).first()
    context = {"active": "map", "return_to": safe_return(request)}
    if lot is None:
        return render(request, "auctions/not_found.html", context, status=404)
    template = "auctions/_lot_detail.html" if request.GET.get("fragment") == "1" else "auctions/detail.html"
    return render(request, template, context | {"lot": lot, "court_search": COURT_SEARCH})
