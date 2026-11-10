from datetime import date
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase

from auctions.forms import BoundsForm, EARTH_RADIUS_KM
from auctions.models import AuctionLot


class FilterContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        data = [
            {"public_id": "apt-old", "use": "아파트", "bid": 500_000_000, "sale_date": date(2026, 10, 1)},
            {"public_id": "apt-new", "use": "아파트", "bid": 499_999_999, "sale_date": date(2026, 10, 2)},
            {"public_id": "office-next", "use": "오피스텔", "minimum": 300_000_000, "auction_date": date(2026, 11, 13)},
        ]
        for row in data:
            AuctionLot.objects.create(source_key=row["public_id"], name=row["public_id"], region="인천", **row)

    def test_home_budget_options_and_use_categories_follow_available_status(self):
        response = self.client.get("/")
        self.assertContains(response, '<option value="50000">5억 원</option>', html=True)
        categories = {row["use"]: (row["kind"], row["count"]) for row in response.context["categories"]}
        self.assertEqual(categories["아파트"], ("sold", 2))
        self.assertEqual(categories["오피스텔"], ("upcoming", 1))

    def test_sold_map_can_choose_a_recorded_sale_date(self):
        response = self.client.get("/map/", {"kind": "sold", "sale_date": "2026-10-01"})
        self.assertEqual([row.public_id for row in response.context["lots"]], ["apt-old"])
        self.assertContains(response, 'id="map-clear-range"')
        self.assertContains(response, '<option value="2026-10-02">2026-10-02</option>', html=True)

    def test_results_price_bands_and_status_links_preserve_intended_filters(self):
        response = self.client.get("/results/", {"status": "sold", "price_band": "3-5", "region": "인천"})
        self.assertEqual([row.public_id for row in response.context["lots"]], ["apt-new"])
        response = self.client.get("/results/", {
            "status": "upcoming", "price_band": "3-5", "region": "인천", "sort": "price-low",
        })
        links = {entry["value"]: parse_qs(urlsplit(entry["url"]).query) for entry in response.context["status_tabs"]}
        self.assertEqual(links["pending"]["price_band"], ["3-5"])
        self.assertEqual(links["pending"]["sort"], ["price-low"])
        self.assertEqual(links["sold"], {"status": ["sold"], "region": ["인천"]})

    def test_extent_threshold_has_a_strict_thirty_kilometre_cap(self):
        from math import degrees

        for distance, expected in [(29.9, True), (30, True), (30.1, False)]:
            with self.subTest(distance=distance):
                box = BoundsForm({
                    "west": 126.5, "east": 126.6, "south": 37.4,
                    "north": 37.4 + degrees(distance / EARTH_RADIUS_KM),
                })
                self.assertEqual(box.is_valid(), expected)
