from datetime import date, timedelta

from django.contrib.gis.geos import Polygon
from django.db.models import Case, Count, DecimalField, F, Q, Value, When
from django.db.models.functions import Cast, NullIf, Replace

from .forms import PRICE_BANDS, RATE_BANDS
from .models import AuctionLot, LotUse


SNAPSHOT_DATE = date(2026, 11, 10)
COURT_SEARCH = "https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ159M00.xml"
MAP_LIMIT = 100


def filter_terms(lots, text):
    if not text:
        return lots
    lots = lots.alias(case_digits=Replace("case_number", Value("타경"), Value("")))
    for term in text.split():
        condition = (
            Q(name__icontains=term) | Q(region__icontains=term)
            | Q(district__icontains=term) | Q(neighborhood__icontains=term)
            | Q(case_number__icontains=term) | Q(court__icontains=term)
        )
        if term.isascii() and term.isdigit():
            condition |= Q(case_digits__contains=term)
        lots = lots.filter(condition)
    return lots


def map_lots(filters, bbox=None, as_of=SNAPSHOT_DATE):
    lots = AuctionLot.objects.all()
    kind = filters["kind"]
    if kind == "upcoming":
        lots = lots.filter(bid__isnull=True, auction_date__gte=as_of)
    elif kind == "sold":
        lots = lots.filter(bid__isnull=False)

    for field in ("region", "use"):
        if filters.get(field):
            lots = lots.filter(**{field: filters[field]})

    if filters.get("budget") is not None:
        cap = filters["budget"] * 10_000
        lots = lots.filter(Q(bid__lte=cap) | Q(bid__isnull=True, minimum__lte=cap))

    if days := filters.get("days"):
        end = as_of + timedelta(days=days)
        start = as_of - timedelta(days=days)
        lots = lots.filter(
            Q(bid__isnull=True, auction_date__range=(as_of, end))
            | Q(bid__isnull=False, sale_date__range=(start, as_of))
        )
    if filters.get("sale_date"):
        lots = lots.filter(sale_date=filters["sale_date"])

    if bbox:
        viewport = Polygon.from_bbox(bbox)
        viewport.srid = 4326
        lots = lots.filter(location__intersects=viewport)

    lots = filter_terms(lots, filters.get("q"))
    if kind == "sold":
        return lots.order_by(F("sale_date").desc(nulls_last=True), "public_id")
    return lots.order_by(
        Case(When(bid__isnull=True, then=Value(0)), default=Value(1)),
        F("auction_date").asc(nulls_last=True), F("sale_date").desc(nulls_last=True), "public_id",
    )


def page_lots(queryset):
    rows = list(queryset[:MAP_LIMIT + 1])
    return rows[:MAP_LIMIT], len(rows) > MAP_LIMIT


def home_categories(upcoming, sold):
    def counts(queryset):
        return dict(queryset.order_by().values_list("use").annotate(count=Count("pk")))

    future, past = counts(upcoming), counts(sold)
    return [
        {"use": use, "kind": "upcoming" if future.get(use) else "sold",
         "count": future.get(use) or past.get(use, 0)}
        for use in LotUse.values
    ]


def result_states(day):
    return {
        "upcoming": Q(bid__isnull=True, auction_date__gt=day),
        "pending": Q(bid__isnull=True, auction_date__lte=day),
        "sold": Q(bid__isnull=False),
        "undated": Q(bid__isnull=True, auction_date__isnull=True),
    }


def result_lots(filters, day):
    status = filters["status"]
    lots = AuctionLot.objects.filter(result_states(day)[status])
    sold = status == "sold"
    if sold:
        lots = lots.annotate(
            rate=Cast(F("bid"), DecimalField(max_digits=25, decimal_places=4)) * 100 / NullIf(F("appraisal"), 0),
        )
    for field in ("region", "use"):
        if filters[field]:
            lots = lots.filter(**{field: filters[field]})
    price = "bid" if sold else "minimum"
    bands = [(price, PRICE_BANDS.get(filters["price_band"]), 100_000_000)]
    if sold:
        bands.append(("rate", RATE_BANDS.get(filters["rate_band"]), 1))
    for field, band, scale in bands:
        if band is not None:
            low, high = band
            if low is not None:
                lots = lots.filter(**{f"{field}__gte": low * scale})
            if high is not None:
                lots = lots.filter(**{f"{field}__lt": high * scale})
    for bound, comparison in (("min", "gte"), ("max", "lte")):
        if (amount := filters[f"{bound}_price"]) is not None:
            lots = lots.filter(**{f"{price}__{comparison}": int(amount * 10_000)})
        if sold and (rate := filters[f"{bound}_rate"]) is not None:
            lots = lots.filter(**{f"rate__{comparison}": rate})
    date_order = F("sale_date").desc(nulls_last=True) if sold else F("auction_date").asc(nulls_last=True)
    ordering = {
        "price-low": [F(price).asc(nulls_last=True)],
        "price-high": [F(price).desc(nulls_last=True)],
    }.get(filters["sort"], [])
    return lots.order_by(*ordering, date_order, "public_id")
