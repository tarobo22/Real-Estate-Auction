from datetime import date

from django.test import TestCase

from auctions.models import AuctionLot

from .test_comparison import choose


class InquiryTests(TestCase):
    def test_empty_pool_gives_editable_generic_draft(self):
        response = self.client.get("/vs/inquiry/")
        self.assertContains(response, "<textarea")
        self.assertContains(response, "경매 물건에 대해 문의드립니다.")
        self.assertContains(response, "문의 내용 복사")

    def test_pair_then_latest_winner_fills_name_and_case_number(self):
        for index in range(2):
            AuctionLot.objects.create(
                public_id=f"item-{index}", source_key=f"item-{index}",
                name=f"비교아파트{index}", region="인천", use="아파트",
                court="인천지법", case_number=f"2026타경77{index}",
                auction_date=date(2026, 11, 15),
            )
        comparison = self.client.get("/vs/")
        self.assertContains(comparison, "바로 문의하기")
        response = self.client.get("/vs/inquiry/")
        self.assertContains(response, "비교아파트0 · 인천지법 2026타경770")
        self.assertContains(response, "비교아파트1 · 인천지법 2026타경771")
        round_ = comparison.context["current_round"]
        self.assertEqual(choose(self.client, round_, "item-0").status_code, 302)
        response = self.client.get("/vs/inquiry/")
        self.assertContains(response, "비교아파트0 · 인천지법 2026타경770")
        self.assertNotContains(response, "2026타경771")
