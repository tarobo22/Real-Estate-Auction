from urllib.parse import urlencode

from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe

from .forms import ResultsFilter
from .models import AuctionLot
from .queries import result_lots, result_states


def status_tabs(data, selected, day):
    counts = AuctionLot.objects.aggregate(**{
        value: Count("pk", filter=condition) for value, condition in result_states(day).items()
    })
    for value, label in ResultsFilter.STATUS_CHOICES:
        fields = ["region", "use"]
        if selected == value or {selected, value} == {"upcoming", "pending"}:
            fields += ["price_band", "min_price", "max_price", "sort"]
        if selected == value == "sold":
            fields += ["rate_band", "min_rate", "max_rate"]
        params = {"status": value} | {key: data[key] for key in fields if data.get(key)}
        yield {"value": value, "label": label, "count": counts[value], "url": "?" + urlencode(params)}


@require_safe
def results(request):
    form = ResultsFilter(request.GET)
    valid = form.is_valid()
    status = form.cleaned_data.get("status") or "upcoming"
    day = timezone.localdate()
    lots = result_lots(form.cleaned_data, day) if valid else []
    return render(request, "auctions/results.html", {
        "filter": form, "status": status, "status_tabs": list(status_tabs(request.GET, status, day)), "lots": lots,
        "return_to": request.get_full_path(), "active": "results",
    }, status=200 if valid else 400)
