from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

from django.db import connections
from django.test import Client, TestCase, TransactionTestCase

from auctions.models import AuctionLot


def create_lots():
    for index in range(6):
        sold = index >= 3
        AuctionLot.objects.create(
            public_id=f"lot-{index}", source_key=f"lot-{index}", name=f"공개단지{index}",
            region="서울" if sold else "인천", use="아파트",
            auction_date=None if sold else date(2026, 11, 12 + index),
            sale_date=date(2026, 10, index) if sold else None,
            minimum=300_000_000 + index * 100_000_000,
            bid=200_000_000 + index * 10_000_000 if sold else None,
        )


def choose(client, round_, winner):
    return client.post("/vs/", {"action": "choose", "token": str(round_.token), "winner": winner})


class ComparisonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_lots()

    def test_pairs_same_status_and_next_pair_avoids_last(self):
        round_ = self.client.get("/vs/").context["current_round"]
        self.assertNotEqual(round_.first_id, round_.second_id)
        self.assertEqual(round_.first.bid is None, round_.second.bid is None)
        self.assertEqual(choose(self.client, round_, round_.first.public_id).status_code, 302)
        next_round = self.client.get("/vs/").context["current_round"]
        self.assertNotEqual({round_.first_id, round_.second_id}, {next_round.first_id, next_round.second_id})

    def test_winner_must_be_in_round_and_session_and_tokens_are_single_use(self):
        round_ = self.client.get("/vs/").context["current_round"]
        winner = round_.first.public_id
        self.assertEqual(choose(Client(), round_, winner).status_code, 400)
        self.assertEqual(choose(self.client, round_, "lot-5").status_code, 400)
        self.assertEqual(choose(self.client, round_, winner).status_code, 302)
        self.assertEqual(choose(self.client, round_, winner).status_code, 409)
        waiting = self.client.get("/vs/").context["current_round"]
        self.assertEqual(self.client.post("/vs/", {"action": "reset"}).status_code, 302)
        self.assertEqual(choose(self.client, waiting, waiting.first.public_id).status_code, 400)
        self.assertEqual(self.client.get("/vs/").context["unique_count"], 0)

    def test_repeat_winner_leaves_two_rounds_and_one_unique_lot(self):
        AuctionLot.objects.exclude(public_id__in=["lot-0", "lot-1"]).delete()
        for _ in range(2):
            round_ = self.client.get("/vs/").context["current_round"]
            self.assertEqual(choose(self.client, round_, "lot-0").status_code, 302)
        response = self.client.get("/vs/")
        self.assertEqual(response.context["unique_count"], 1)
        self.assertEqual(len(response.context["history"]), 2)

class ConcurrentRoundTests(TransactionTestCase):
    def test_simultaneous_round_submissions_can_record_only_one_winner(self):
        create_lots()
        round_ = self.client.get("/vs/").context["current_round"]
        cookies = self.client.cookies.copy()
        barrier = Barrier(2, timeout=10)

        def submit(public_id):
            try:
                client = Client()
                client.cookies.update(cookies)
                barrier.wait()
                return choose(client, round_, public_id).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(submit, [round_.first.public_id, round_.second.public_id]))
        self.assertEqual(sorted(outcomes), [302, 409])
        self.assertEqual(self.client.get("/vs/").context["unique_count"], 1)
