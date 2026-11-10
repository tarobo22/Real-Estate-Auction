from uuid import uuid4

from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GistIndex
from django.db.models import F, Func, Q, Value


class Region(models.TextChoices):
    SEOUL = "서울"
    GYEONGGI = "경기"
    INCHEON = "인천"


class LotUse(models.TextChoices):
    APARTMENT = "아파트"
    OFFICE = "오피스텔"
    MULTIFAMILY = "연립·다세대"
    COMMERCIAL = "상가"
    LAND = "토지"


def won_label(amount):
    if amount is None:
        return "미수록"
    hundred_millions, remainder = divmod(amount, 100_000_000)
    ten_thousands, won = divmod(remainder, 10_000)
    parts = []
    if hundred_millions:
        parts.append(f"{hundred_millions:,}억")
    if ten_thousands:
        parts.append(f"{ten_thousands:,}만")
    if won or not parts:
        parts.append(f"{won:,}")
    return " ".join(parts) + ("원" if won or not amount else " 원")


class AuctionLot(models.Model):
    public_id = models.SlugField(max_length=48, unique=True)
    source_key = models.CharField(max_length=512, unique=True)
    name = models.CharField(max_length=160)
    region = models.CharField(max_length=12, choices=Region)
    district = models.CharField(max_length=64)
    neighborhood = models.CharField(max_length=48, blank=True)
    use = models.CharField(max_length=16, choices=LotUse)
    court = models.CharField(max_length=48, blank=True)
    court_code = models.CharField(max_length=16, blank=True)
    case_number = models.CharField(max_length=32, blank=True)
    lot_number = models.PositiveSmallIntegerField(null=True, blank=True)
    auction_date = models.DateField(null=True, blank=True)
    sale_date = models.DateField(null=True, blank=True)
    checked_on = models.DateField(null=True, blank=True)
    appraisal = models.PositiveBigIntegerField(null=True, blank=True)
    minimum = models.PositiveBigIntegerField(null=True, blank=True)
    bid = models.PositiveBigIntegerField(null=True, blank=True)
    area = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    floor = models.SmallIntegerField(null=True, blank=True)
    failed = models.PositiveSmallIntegerField(null=True, blank=True)
    note = models.TextField(blank=True)
    advantage = models.CharField(max_length=180, blank=True)
    trade_note = models.TextField(blank=True)
    court_url = models.URLField(max_length=512, blank=True)
    reference_urls = models.JSONField(default=list, blank=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    # PostgreSQL derives the indexed geometry from the imported WGS84 coordinates.
    location = models.GeneratedField(
        expression=Func(
            Func(F("longitude"), F("latitude"), function="ST_MakePoint", output_field=models.PointField()),
            Value(4326),
            function="ST_SetSRID",
            output_field=models.PointField(srid=4326),
        ),
        output_field=models.PointField(srid=4326, spatial_index=False),
        db_persist=True,
        null=True,
    )

    class Meta:
        indexes = [GistIndex(fields=["location"], name="auction_lot_location_gist")]
        constraints = [
            models.UniqueConstraint(
                fields=["court_code", "case_number", "lot_number"],
                condition=Q(lot_number__isnull=False) & ~Q(court_code="") & ~Q(case_number=""),
                name="auction_unique_court_case_lot",
            ),
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(
                        latitude__isnull=False, longitude__isnull=False,
                        latitude__range=(-90, 90), longitude__range=(-180, 180),
                    )
                ),
                name="auction_valid_wgs84_pair",
            ),
        ]

    @property
    def address(self):
        return " ".join(filter(None, (self.region, self.district, self.neighborhood)))

    @property
    def case_label(self):
        identity = " ".join(filter(None, (self.court, self.case_number)))
        return f"{identity} · 물건 {self.lot_number}" if self.lot_number else identity

    @property
    def price(self):
        return self.minimum if self.bid is None else self.bid

    @property
    def price_label(self):
        return "최저입찰가" if self.bid is None else "실제 낙찰가"

    @property
    def display_price(self):
        return won_label(self.price)

    @property
    def display_minimum(self):
        return won_label(self.minimum)

    @property
    def display_appraisal(self):
        return won_label(self.appraisal)

    @property
    def display_bid(self):
        return won_label(self.bid)


class ComparableSale(models.Model):
    lot = models.ForeignKey(AuctionLot, on_delete=models.CASCADE, related_name="comparable_sales")
    source_url = models.URLField(max_length=512)
    sale_date = models.DateField()
    price = models.PositiveBigIntegerField()
    floor = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-sale_date", "pk"]

    @property
    def display_price(self):
        return won_label(self.price)


class AuctionEvent(models.Model):
    class Kind(models.TextChoices):
        SCHEDULED = "scheduled", "기일 공고"
        RESCHEDULED = "rescheduled", "기일 변경"
        FAILED = "failed", "유찰"
        SOLD = "sold", "낙찰"
        UNPAID = "unpaid", "미납"
        WITHDRAWN = "withdrawn", "취하"

    lot = models.ForeignKey(AuctionLot, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=16, choices=Kind)
    occurred_on = models.DateField()
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-occurred_on", "-pk"]
        constraints = [models.UniqueConstraint(
            fields=["lot", "kind", "occurred_on"], name="auction_unique_lot_event",
        )]


class CartItem(models.Model):
    session = models.ForeignKey("sessions.Session", on_delete=models.CASCADE)
    lot = models.ForeignKey(AuctionLot, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "lot"], name="auction_unique_cart_lot")]


class ComparisonRound(models.Model):
    session = models.ForeignKey("sessions.Session", on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    first = models.ForeignKey(AuctionLot, on_delete=models.CASCADE, related_name="+")
    second = models.ForeignKey(AuctionLot, on_delete=models.CASCADE, related_name="+")
    winner = models.ForeignKey(AuctionLot, null=True, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session"], condition=Q(winner__isnull=True), name="auction_one_open_round",
            ),
            models.CheckConstraint(condition=~Q(first=F("second")), name="auction_round_distinct_lots"),
            models.CheckConstraint(
                condition=Q(winner__isnull=True) | Q(winner=F("first")) | Q(winner=F("second")),
                name="auction_winner_belongs_to_round",
            ),
        ]


class BriefingThread(models.Model):
    class Scope(models.TextChoices):
        ALL = "all", "전체"
        WINNERS = "winners", "이긴 매물"

    session = models.ForeignKey("sessions.Session", on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    scope = models.CharField(max_length=8, choices=Scope)
    title = models.CharField(max_length=80)
    updated_at = models.DateTimeField(auto_now=True)


class BriefingExchange(models.Model):
    thread = models.ForeignKey(BriefingThread, on_delete=models.CASCADE, related_name="exchanges")
    question = models.CharField(max_length=240)
    answer = models.TextField()
    lot_ids = models.JSONField(default=list)
