from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from auctions.models import DEMO_SOURCE_PREFIX, AuctionEvent, AuctionLot, LotUse, Region
from auctions.queries import SNAPSHOT_DATE


# Coordinates are approximate district anchors for the map demo.
DISTRICTS = (
    ("songpa", Region.SEOUL, "송파구", "37.5100", "127.1100", 350_000_000),
    ("yangcheon", Region.SEOUL, "양천구", "37.5230", "126.8600", 220_000_000),
    ("nowon", Region.SEOUL, "노원구", "37.6540", "127.0660", 120_000_000),
    ("gangdong", Region.SEOUL, "강동구", "37.5380", "127.1350", 160_000_000),
    ("guri", Region.GYEONGGI, "구리시", "37.6010", "127.1390", 85_000_000),
    ("bundang", Region.GYEONGGI, "성남시 분당구", "37.3840", "127.1230", 195_000_000),
    ("giheung", Region.GYEONGGI, "용인시 기흥구", "37.2840", "127.1160", 70_000_000),
    ("yeongtong", Region.GYEONGGI, "수원시 영통구", "37.2550", "127.0620", 95_000_000),
    ("michuhol", Region.INCHEON, "미추홀구", "37.4480", "126.6820", 15_000_000),
    ("yeonsu", Region.INCHEON, "연수구", "37.4090", "126.6760", 85_000_000),
    ("namdong", Region.INCHEON, "남동구", "37.4410", "126.7280", 30_000_000),
    ("bupyeong", Region.INCHEON, "부평구", "37.4950", "126.7220", 50_000_000),
)

PROPERTY_TYPES = (
    ("apartment", LotUse.APARTMENT, 340_000_000, ("59.94", "84.95", "112.23"), (4, 9, 16)),
    ("officetel", LotUse.OFFICE, 145_000_000, ("24.71", "39.82", "52.06"), (3, 7, 12)),
    ("villa", LotUse.MULTIFAMILY, 130_000_000, ("38.65", "51.24", "68.13"), (1, 2, 4)),
    ("retail", LotUse.COMMERCIAL, 210_000_000, ("32.90", "58.40", "92.75"), (1, 2, 3)),
    ("land", LotUse.LAND, 90_000_000, ("155.00", "310.00", "560.00"), (None, None, None)),
)


class Command(BaseCommand):
    help = "입찰랩에 가상 시연 매물 60건을 적재합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        for district_index, (district_key, region, district, lat, lon, premium) in enumerate(DISTRICTS):
            for type_index, (type_key, use, base_price, areas, floors) in enumerate(PROPERTY_TYPES):
                variant = (district_index + type_index) % 3
                sold = (district_index + type_index) % len(PROPERTY_TYPES) < 2
                sequence = district_index * len(PROPERTY_TYPES) + type_index
                day_offset = -5 - sequence * 2 if sold else 2 + sequence * 2
                occurred_on = SNAPSHOT_DATE + timedelta(days=day_offset)
                appraisal = base_price + premium + 12_000_000 * variant
                minimum = appraisal * (100, 80, 64)[variant] // 100
                bid = minimum + (appraisal - minimum) // 3 + 3_000_000 if sold else None
                values = {
                    "name": f"[시연] {district} {use}",
                    "region": region,
                    "district": district,
                    "use": use,
                    "case_number": f"DEMO-{district_index + 1:02d}-{type_index + 1:02d}",
                    "auction_date": None if sold else occurred_on,
                    "sale_date": occurred_on if sold else None,
                    "appraisal": appraisal,
                    "minimum": minimum,
                    "bid": bid,
                    "area": Decimal(areas[variant]),
                    "floor": floors[variant],
                    "failed": variant,
                    "latitude": Decimal(lat) + Decimal("0.001") * (type_index - 2),
                    "longitude": Decimal(lon) + Decimal("0.002") * (type_index - 2),
                }
                lot, _ = AuctionLot.objects.update_or_create(
                    source_key=f"{DEMO_SOURCE_PREFIX}{district_key}:{type_key}",
                    defaults=values,
                    create_defaults={"public_id": f"demo-{district_key}-{type_key}", **values},
                )
                AuctionEvent.objects.update_or_create(
                    lot=lot,
                    kind=AuctionEvent.Kind.SOLD if sold else AuctionEvent.Kind.SCHEDULED,
                    occurred_on=occurred_on,
                    defaults={"note": "시연 데이터"},
                )
        self.stdout.write(self.style.SUCCESS(
            f"시연 매물 {len(DISTRICTS) * len(PROPERTY_TYPES)}건을 적재했습니다."
        ))
