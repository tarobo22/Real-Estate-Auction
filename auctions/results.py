from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe

from .forms import ResultsFilter
from .queries import result_lots


@require_safe
def results(request):
    form = ResultsFilter(request.GET)
    valid = form.is_valid()
    status = form.cleaned_data.get("status") or "upcoming"
    lots = result_lots(form.cleaned_data, timezone.localdate()) if valid else []
    return render(request, "auctions/results.html", {
        "filter": form, "status": status, "statuses": ResultsFilter.STATUS_CHOICES, "lots": lots,
        "return_to": request.get_full_path(), "active": "results",
    }, status=200 if valid else 400)
