import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from auctions.models import AuctionEvent, AuctionLot, ComparableSale
from auctions.queries import SNAPSHOT_DATE


SOURCE_FILE = Path(__file__).resolve().parents[2] / "data" / "public_snapshot.json"
CASE = re.compile(r"(?P<court>.+?) (?P<case>\d{4}타경\d+)(?: · 물건 (?P<lot>\d+))?")
COURT_CODES = {
    "서울동부지법": "B000211",
    "남양주지원": "B214804",
    "인천지법": "B000240",
    "수원지법": "B000250",
    "수원지법 성남지원": "B000251",
}
validate_url = URLValidator(schemes=["https"])


def won(value):
    if value is None:
        return None
    amount = Decimal(str(value)) * 10_000
    if amount < 0 or amount != amount.to_integral_value():
        raise CommandError(f"원 단위로 변환할 수 없는 금액입니다. {value}")
    return int(amount)


class Command(BaseCommand):
    help = "입찰랩 공개 경매 사례 스냅샷을 적재합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        rows = json.loads(SOURCE_FILE.read_text(encoding="utf-8"), parse_float=Decimal)
        for row in rows:
            identity = CASE.fullmatch(row["caseNumber"])
            if not identity:
                raise CommandError(f"사건번호를 확인해 주세요. {row['id']}")
            sources = row["sources"]
            for url in sources:
                validate_url(url)
            court = identity["court"]
            sale = row["kind"] == "sold"
            day = date.fromisoformat(row["date"])
            values = {
                "name": row["name"], "region": row["region"], "district": row["district"],
                "neighborhood": row.get("neighborhood", ""), "use": row["use"],
                "court": court, "court_code": COURT_CODES.get(court, ""),
                "case_number": identity["case"], "lot_number": identity["lot"],
                "auction_date": None if sale else day, "sale_date": day if sale else None,
                "checked_on": SNAPSHOT_DATE,
                "appraisal": won(row.get("appraisal")), "minimum": won(row.get("minimum")),
                "bid": won(row.get("bid")), "area": row.get("area"), "floor": row.get("floor"),
                "failed": row.get("failed"), "latitude": row.get("lat"), "longitude": row.get("lon"),
                "note": row.get("note", ""), "trade_note": row.get("tradeNote", ""),
                "advantage": row.get("advantage", ""), "reference_urls": sources,
            }
            lot, _ = AuctionLot.objects.update_or_create(
                source_key=sources[0],
                defaults=values,
                create_defaults={"public_id": row["id"], **values},
            )
            AuctionEvent.objects.update_or_create(
                lot=lot, kind=AuctionEvent.Kind.SOLD if sale else AuctionEvent.Kind.SCHEDULED,
                occurred_on=day, defaults={"note": row.get("status", "")},
            )
            lot.comparable_sales.all().delete()
            ComparableSale.objects.bulk_create([
                ComparableSale(
                    lot=lot, source_url=sources[1], sale_date=date.fromisoformat(comp["date"]),
                    floor=comp.get("floor"), price=won(comp["price"]),
                )
                for comp in row.get("comps", [])
            ])
        self.stdout.write(self.style.SUCCESS(f"공개 사례 {len(rows)}건을 적재했습니다."))
