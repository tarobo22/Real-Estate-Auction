from django.test import Client, TestCase

from auctions.models import AuctionLot

from .test_comparison import choose, create_lots


class BriefingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_lots()

    def test_five_unique_winners_enable_recommendation_and_remove_disables_it(self):
        seen = set()
        for _ in range(5):
            round_ = self.client.get("/vs/").context["current_round"]
            available = {round_.first.public_id, round_.second.public_id} - seen
            winner = min(available)
            seen.add(winner)
            response = choose(self.client, round_, winner)
        self.assertRedirects(response, "/vs/?recommend=1")
        response = self.client.get("/vs/?recommend=1")
        self.assertEqual(response.context["unique_count"], 5)
        self.assertContains(response, "AI 추천받기")
        self.assertContains(response, "이긴 매물로 브리핑")
        record = response.context["history"][0]
        self.client.post("/vs/", {"action": "remove", "token": str(record.token)})
        self.assertEqual(self.client.get("/vs/").context["unique_count"], 4)
        self.assertNotContains(self.client.get("/vs/"), "AI 추천받기")

    def test_briefing_uses_server_scope_and_recovers_only_own_threads(self):
        question = "인천 아파트 5억 이하 찾아줘"
        response = self.client.post("/briefing/", {"question": question, "scope": "all"})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), question)
        self.assertContains(self.client.get(response.url), "공개단지0")
        self.assertEqual(Client().get(response.url).status_code, 404)
        response = self.client.post("/briefing/", {"question": question, "scope": "winners", "ids": "lot-0"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "고유한 매물 5건", status_code=400)

    def test_rule_query_distinguishes_inclusive_and_strict_budget(self):
        for phrase, expected in [("이하", ["lot-0", "lot-1", "lot-2"]), ("미만", ["lot-0", "lot-1"])]:
            with self.subTest(phrase=phrase):
                response = self.client.post("/briefing/", {"question": f"인천 아파트 5억 {phrase}", "scope": "all"})
                self.assertEqual(response.status_code, 302)
                messages = self.client.get(response.url).context["messages"]
                self.assertEqual(messages[0][0].lot_ids, expected)

    def test_qualified_candidate_query_cannot_include_unselected_lot(self):
        seen = set()
        for _ in range(5):
            round_ = self.client.get("/vs/").context["current_round"]
            winner = min({round_.first.public_id, round_.second.public_id} - seen)
            seen.add(winner)
            choose(self.client, round_, winner)
        recommendation = self.client.get("/vs/").context["recommended"]
        self.assertEqual([lot.public_id for lot in recommendation], ["lot-0", "lot-1"])
        other = AuctionLot.objects.exclude(public_id__in=seen).get()
        response = self.client.post("/briefing/", {
            "scope": "winners", "question": other.name + " 보여줘", "ids": other.public_id,
        })
        self.assertEqual(response.status_code, 302)
        exchange, _ = self.client.get(response.url).context["messages"][0]
        self.assertEqual(exchange.lot_ids, [])
