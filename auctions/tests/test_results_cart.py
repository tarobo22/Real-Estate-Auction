from datetime import UTC, date, datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase

from auctions.models import AuctionLot


class ResultsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        examples = [
            {"public_id": "tomorrow", "auction_date": date(2026, 11, 11), "minimum": 500_000_000},
            {"public_id": "later", "auction_date": date(2026, 11, 15), "minimum": 500_000_001},
            {"public_id": "undated", "minimum": 300_000_000},
            {"public_id": "closed", "bid": 260_336_000, "appraisal": 325_420_000, "sale_date": date(2026, 10, 19)},
            {"public_id": "unknown-rate", "bid": 200_000_000, "appraisal": 0, "sale_date": date(2026, 10, 20)},
        ]
        for values in examples:
            AuctionLot.objects.create(
                source_key=values["public_id"], name=values["public_id"], region="인천", use="아파트", **values,
            )

    def test_seoul_midnight_switches_from_upcoming_to_pending(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 10, 14, 59, tzinfo=UTC)):
            response = self.client.get("/results/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row.public_id for row in response.context["lots"]], ["tomorrow", "later"])
        with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 10, 15, 0, tzinfo=UTC)):
            response = self.client.get("/results/", {"status": "pending", "max_price": "50000", "min_rate": "99"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row.public_id for row in response.context["lots"]], ["tomorrow"])
            self.assertContains(response, "최저입찰가")
            self.assertNotContains(response, 'name="min_rate"')

    def test_sold_filters_by_bid_and_ratio_including_exact_boundaries(self):
        response = self.client.get("/results/", {"status": "sold", "max_price": "26033.6", "min_rate": "80"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row.public_id for row in response.context["lots"]], ["closed"])
        self.assertContains(response, "실제 낙찰가")
        self.assertContains(response, "80.0%")
        response = self.client.get("/results/", {"status": "sold"})
        self.assertIsNone(response.context["lots"][0].rate)

    def test_case_timeline_is_seeded_without_inventing_unknown_dates(self):
        for _ in range(2):
            call_command("seed_auctions", stdout=StringIO())
        response = self.client.get("/lots/so1/")
        self.assertContains(response, "사건 이력")
        lot = response.context["lot"]
        self.assertEqual(list(lot.events.values_list("kind", flat=True)), ["sold"])

    def test_demo_prices_and_photos_stay_labeled_in_home_results_and_detail(self):
        demo = AuctionLot.objects.create(
            public_id="test-demo", source_key="demo:auction-lab:test", name="[시연] 확인용 토지",
            region="인천", use="토지", bid=300_000_000, sale_date=date(2026, 10, 21),
        )
        home = self.client.get("/")
        self.assertContains(home, "AI 예시 사진")
        self.assertNotContains(home, "실제 낙찰 사례")
        self.assertContains(self.client.get("/results/", {"status": "sold"}), "시연 낙찰가")
        detail = self.client.get(f"/lots/{demo.public_id}/")
        self.assertContains(detail, "시연용 가상 매물")
        self.assertContains(detail, "demo-land.webp")
        self.assertNotContains(detail, "법원경매정보 통합 검색")
        self.assertNotContains(detail, "비교 매매 실거래")


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for public_id in ("a", "b"):
            AuctionLot.objects.create(
                public_id=public_id, source_key=public_id, name="관심 물건 " + public_id,
                region="서울", use="아파트", minimum=300_000_000,
            )

    def update(self, action, public_id=""):
        return self.client.post("/cart/", {"action": action, "lot": public_id}, HTTP_ACCEPT="application/json")

    def test_add_is_idempotent_and_visible_only_in_same_browser(self):
        self.assertEqual(self.update("add", "a").status_code, 200)
        self.assertEqual(self.update("add", "a").json()["ids"], ["a"])
        self.assertContains(self.client.get("/lots/a/"), "장바구니에서 빼기")
        self.assertContains(self.client.get("/cart/"), "관심 물건 a")
        self.assertNotContains(Client().get("/cart/"), "관심 물건 a")
        self.assertEqual(self.update("add", "b").json()["count"], 2)
        self.assertEqual(self.update("remove", "a").json()["ids"], ["b"])
        self.assertEqual(self.update("clear").json()["ids"], [])

    def test_invalid_actions_unknown_lots_and_cross_site_mutation(self):
        self.assertEqual(self.update("unknown", "a").status_code, 400)
        self.assertEqual(self.update("add", "missing").status_code, 404)
        self.assertEqual(Client(enforce_csrf_checks=True).post("/cart/", {"action": "add", "lot": "a"}).status_code, 403)
        response = self.client.post("/cart/", {"action": "add", "lot": "a", "return_to": "//example.org/"})
        self.assertRedirects(response, "/cart/")
