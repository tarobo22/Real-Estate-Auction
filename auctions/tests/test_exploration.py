from datetime import date
from decimal import Decimal
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase


class EntryTests(TestCase):
    def test_home_uses_shareable_map_form(self):
        response = self.client.get("/")
        self.assertContains(response, 'action="/map/"')
        self.assertContains(response, 'name="budget"')
        self.assertRedirects(self.client.get("/about.html"), "/")


class ExplorationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lots = apps.get_model("auctions", "AuctionLot")
        for slug, price, overrides in [
            ("below", 499_999_999, {}),
            ("ceiling", 500_000_000, {}),
            ("above", 500_000_001, {}),
            ("elsewhere", 400_000_000, {"region": "서울"}),
            ("other-use", 300_000_000, {"use": "상가"}),
            ("no-pin", 400_000_000, {"latitude": None, "longitude": None}),
            ("outside", 400_000_000, {"longitude": Decimal("126.900000")}),
        ]:
            values = {
                "public_id": slug, "source_key": slug, "name": "바다아파트",
                "region": "인천", "district": "연수구", "use": "아파트",
                "court": "인천지법", "case_number": "2026타경1234",
                "auction_date": date(2026, 11, 19), "minimum": price,
                "latitude": Decimal("37.400000"), "longitude": Decimal("126.600000"),
            }
            cls.lots.objects.create(**(values | overrides))

    def test_shareable_query_uses_inclusive_won_budget_and_combines_terms(self):
        response = self.client.get("/map/", {
            "region": "인천", "use": "아파트", "budget": "50000", "q": "바다 20261234",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {lot.public_id for lot in response.context["lots"]},
            {"below", "ceiling", "no-pin", "outside"},
        )
        self.assertEqual({pin["id"] for pin in response.context["pins"]}, {"below", "ceiling", "outside"})

    def test_bounds_include_edges_and_exclude_unlocated_lots(self):
        response = self.client.get("/api/map/lots/", {
            "west": "126.6", "south": "37.4", "east": "126.8", "north": "37.6",
            "region": "인천", "use": "아파트", "budget": "50000",
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual({lot["id"] for lot in body["lots"]}, {"below", "ceiling"})
        self.assertEqual(body["limit"], 100)
        self.assertFalse(body["truncated"])
        self.assertEqual({lot["price_label"] for lot in body["lots"]}, {"최저입찰가"})

    def test_bad_bounds_are_distinct_from_empty_results(self):
        valid = {"west": "126.6", "south": "37.4", "east": "126.8", "north": "37.6"}
        for change in [
            {"east": "126.6"}, {"east": "127.0"}, {"north": "37.7"},
            {"west": "-181"}, {"south": ""}, {"west": "NaN"},
        ]:
            with self.subTest(change=change):
                response = self.client.get("/api/map/lots/", valid | change)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.json()["errors"])
        response = self.client.get("/api/map/lots/", valid | {"q": "일치하지 않음"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lots"], [])

    def test_detail_and_fragment_share_source_and_missing_data(self):
        for suffix in ("", "?fragment=1"):
            response = self.client.get("/lots/ceiling/" + suffix)
            self.assertContains(response, "2026타경1234")
            self.assertContains(response, "법원경매정보 통합 검색")
            self.assertContains(response, "실거래 미수록")
        self.assertContains(self.client.get("/lots/missing/"), "/map/", status_code=404)

    def test_public_snapshot_import_is_repeatable_and_preserves_won_precision(self):
        for _ in range(2):
            call_command("seed_auctions", stdout=StringIO())
        self.assertEqual(self.lots.objects.filter(public_id="so1").count(), 1)
        self.assertEqual(self.lots.objects.get(public_id="so1").bid, 260_336_000)
        self.assertIsNone(self.lots.objects.get(public_id="ri3").lot_number)
