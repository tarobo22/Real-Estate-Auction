from datetime import date
from itertools import combinations
from random import choice
from urllib.parse import urlencode
from uuid import UUID

from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import AuctionLot, ComparisonRound
from .queries import SNAPSHOT_DATE
from .sessions import browser_session, lock_browser_session


RECOMMENDATION_MIN = 5


def recommendations(lots):
    upcoming = [
        lot for lot in lots
        if lot.bid is None and lot.auction_date and lot.auction_date >= SNAPSHOT_DATE
    ]
    dated = sorted(upcoming, key=lambda lot: (lot.auction_date, lot.public_id))
    cheapest = min(
        (lot for lot in dated if lot.minimum is not None),
        key=lambda lot: (lot.minimum, lot.auction_date, lot.public_id),
        default=None,
    )
    primary = ([cheapest] + [lot for lot in dated if lot != cheapest] if cheapest else dated)[:2]
    sold = sorted(
        (lot for lot in lots if lot.bid is not None),
        key=lambda lot: (lot.sale_date or date.min, lot.public_id),
        reverse=True,
    )
    return primary, sold[:2 - len(primary)]


def round_history(session):
    return ComparisonRound.objects.filter(session_id=session, winner__isnull=False)


def winner_ids(session):
    return set(round_history(session).values_list("winner_id", flat=True).order_by())


def select_pair(groups, seen, previous):
    for require_new in (True, False):
        for group in groups:
            ranked = [
                (sum(lot.pk not in seen for lot in pair), pair)
                for pair in combinations(group, 2)
                if frozenset(lot.pk for lot in pair) != previous
            ]
            if ranked:
                best = max(score for score, _ in ranked)
                if best or not require_new:
                    return choice([pair for score, pair in ranked if score == best])
    return next((tuple(group[:2]) for group in groups if len(group) >= 2), None)


def comparison_groups():
    candidates = AuctionLot.objects.order_by("public_id")
    return (
        list(candidates.filter(bid__isnull=True, auction_date__gte=SNAPSHOT_DATE)),
        list(candidates.filter(bid__isnull=False)),
    )


def current_comparison(request):
    groups = comparison_groups()
    single = next((group[0] for group in groups if group), None)
    if not any(len(group) >= 2 for group in groups):
        return None, single
    with transaction.atomic():
        session = lock_browser_session(request)
        rows = ComparisonRound.objects.filter(session=session)
        active = rows.filter(winner__isnull=True).select_related("first", "second").first()
        if active:
            return active, None
        last = rows.order_by("-pk").first()
        previous = frozenset((last.first_id, last.second_id)) if last else frozenset()
        first, second = select_pair(groups, winner_ids(session.pk), previous)
        return ComparisonRound.objects.create(session=session, first=first, second=second), None


def submit_round(request):
    action = request.POST.get("action")
    if action not in {"choose", "remove", "reset"}:
        return HttpResponseBadRequest("비교 동작을 확인해 주세요.")
    session_id = browser_session(request)
    if not session_id:
        return HttpResponseBadRequest("이 브라우저의 비교 라운드를 다시 열어 주세요.")
    with transaction.atomic():
        session = lock_browser_session(request)
        rows = ComparisonRound.objects.filter(session=session)
        if action == "reset":
            rows.delete()
            return redirect("auctions:vs")
        try:
            token = UUID(request.POST.get("token", ""))
        except ValueError:
            return HttpResponseBadRequest("비교 라운드가 올바르지 않습니다.")
        round_ = rows.select_related("first", "second").filter(token=token).first()
        if not round_:
            return HttpResponseBadRequest("이 비교 라운드를 다시 열어 주세요.")
        if action == "remove":
            if round_.winner_id is None:
                return HttpResponseBadRequest("저장된 라운드만 삭제할 수 있습니다.")
            round_.delete()
            return redirect(reverse("auctions:vs") + "#winner-history")
        if round_.winner_id is not None:
            return HttpResponse("이미 저장된 비교입니다. 비교 화면을 다시 열어 주세요.", status=409)
        choice_id = request.POST.get("winner")
        selected = next((lot for lot in (round_.first, round_.second) if lot.public_id == choice_id), None)
        if selected is None:
            return HttpResponseBadRequest("이 라운드의 물건을 선택해 주세요.")
        seen = winner_ids(session.pk)
        round_.winner = selected
        round_.save(update_fields=["winner"])
        next_url = reverse("auctions:vs")
        if len(seen) == RECOMMENDATION_MIN - 1 and selected.pk not in seen:
            next_url += "?" + urlencode({"recommend": "1"})
        return redirect(next_url)


@require_http_methods(["GET", "HEAD", "POST"])
def versus(request):
    if request.method == "POST":
        return submit_round(request)
    round_, single = current_comparison(request)
    session = browser_session(request)
    history = list(round_history(session).select_related("winner").order_by("-pk")) if session else []
    winners = {row.winner_id: row.winner for row in history}
    primary, sold = recommendations(winners.values()) if len(winners) >= RECOMMENDATION_MIN else ([], [])
    return render(request, "auctions/vs.html", {
        "current_round": round_, "single_lot": single, "history": history,
        "unique_count": len(winners), "active": "vs", "recommended": primary, "sold_reference": sold,
    })
