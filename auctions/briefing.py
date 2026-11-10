import re
from decimal import Decimal
from urllib.parse import urlencode
from uuid import UUID

from django.db import transaction
from django.db.models import F, Q
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .comparison import RECOMMENDATION_MIN, winner_ids
from .forms import BriefingForm
from .models import AuctionLot, BriefingExchange, BriefingThread, LotUse, Region
from .queries import SNAPSHOT_DATE, filter_terms
from .sessions import browser_session, lock_browser_session


MAX_THREADS = 30
MAX_EXCHANGES = 20
VISIBLE_RESULTS = 6
BUDGET = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*억(?:\s*(\d+(?:,\d{3})*)\s*(천\s*만?|만))?|(\d+(?:,\d{3})*)\s*만\s*원")
CASE = re.compile(r"\d{4}\s*타경\s*\d+")
STOP_WORDS = re.compile(
    r"이하|미만|이상|초과|추천|목록|사례|경매|수도권|물건|매물|예정|진행중|입찰|낙찰|매각|완료|"
    r"보여\s*줘|찾아\s*줘|알려\s*줘|주세요|어때|비교|차이|상세|실거래|가격|기일|"
    r"그중|그\s*중|첫\s*번째|두\s*번째|이전|최근|근거|해줘|해주세요",
)


def parse_budget(question):
    match = BUDGET.search(question)
    if not match:
        return None
    eok, tail, units, man = match.groups()
    if man:
        return int(man.replace(",", "")) * 10_000
    amount = Decimal(eok.replace(",", "")) * 100_000_000
    if tail:
        amount += int(tail.replace(",", "")) * (10_000_000 if units.startswith("천") else 10_000)
    return int(amount)


def answer_query(question, pool, previous=()):
    compact = re.sub(r"\s+", "", question)
    if any(word in compact for word in ("교통", "학군", "상권", "역세권", "도보", "침수")):
        return "교통·학군·상권 등 입지 조건을 비교할 확인 자료가 부족합니다. 지역이나 예산으로 다시 검색할 수 있어요.", []

    regions = [value for value in Region.values if value in compact]
    uses = [value for value in LotUse.values if value in compact]
    named = [
        pk for pk, name in pool.values_list("pk", "name")
        if name and re.sub(r"\s+", "", name) in compact
    ]
    cases = [re.sub(r"\s+", "", match) for match in CASE.findall(question)]
    budget = parse_budget(question)
    compare = "비교" in compact or "차이" in compact
    sold = any(word in compact for word in ("낙찰", "매각완료", "실제매각가"))
    upcoming = any(word in compact for word in ("입찰예정", "진행중"))
    follow_up = any(word in compact for word in ("그중", "첫번째", "두번째", "이전", "실거래")) or (
        compare and not (regions or uses or named or cases or budget is not None or sold or upcoming)
    )

    rows = pool
    if follow_up:
        if not previous and not (named or cases):
            return "이전에 찾은 물건이 없어요. 비교할 물건이나 단지명을 먼저 알려주세요.", []
        if previous and not (named or cases):
            ids = previous[:1] if "첫번째" in compact else previous[1:2] if "두번째" in compact else previous
            rows = rows.filter(public_id__in=ids)
    if named or cases:
        rows = rows.filter(Q(pk__in=named) | Q(case_number__in=cases))
    if regions:
        rows = rows.filter(region__in=regions)
    if uses:
        rows = rows.filter(use__in=uses)

    terms = BUDGET.sub(" ", question)
    for value in sorted([*regions, *uses], key=len, reverse=True):
        terms = terms.replace(value + "도", " ").replace(value, " ")
    terms = STOP_WORDS.sub(" ", terms)
    terms = re.sub(r"(?<!\w)(?:중|두|건|개|있는|에서|으로|좀|만|원)(?!\w)", " ", terms)
    terms = re.sub(r"[?!.~]", " ", terms).strip()
    if terms and not (named or cases or follow_up):
        rows = filter_terms(rows, terms)

    if sold:
        rows = rows.filter(bid__isnull=False)
    elif upcoming or not (named or cases or follow_up):
        rows = rows.filter(bid__isnull=True, auction_date__gte=SNAPSHOT_DATE)
    if budget is not None:
        comparison = "lt" if "미만" in compact else "gt" if "초과" in compact else "gte" if "이상" in compact else "lte"
        rows = rows.filter(Q(**{f"bid__{comparison}": budget}) | Q(bid__isnull=True, **{f"minimum__{comparison}": budget}))
    ordering = F("sale_date").desc(nulls_last=True) if sold else F("auction_date").asc(nulls_last=True)
    matched = list(rows.order_by(ordering, "public_id"))
    if follow_up and previous and not (named or cases):
        positions = {public_id: position for position, public_id in enumerate(previous)}
        matched.sort(key=lambda lot: positions.get(lot.public_id, len(previous)))
    ids = [lot.public_id for lot in matched]
    if not ids:
        return "수록 자료에서 조건에 맞는 물건을 찾지 못했습니다. 예산이나 지역을 조정해 보세요.", []
    if compare:
        if len(ids) < 2:
            return "비교할 대상이 한 건뿐입니다. 다른 물건을 하나 더 찾아 주세요.", ids
        return "두 물건의 가격 종류와 기일을 구분해 비교했습니다. 각 상세에서 사건번호와 실거래 출처를 확인할 수 있어요.", ids[:2]
    if "실거래" in compact:
        sales = matched[0].comparable_sales.all()[:3]
        labels = [f"{trade.sale_date:%Y.%m.%d} {trade.display_price}" for trade in sales]
        answer = "수록된 비교 실거래는 " + ", ".join(labels) + "입니다." if labels else "이 물건의 비교 실거래는 미수록입니다."
        return answer, ids[:1]
    count = len(ids)
    shown = " 먼저 6건을 표시합니다." if count > VISIBLE_RESULTS else ""
    return f"수록 자료에서 조건에 맞는 물건 {count}건을 찾았습니다.{shown} 가격 기준과 상세 링크를 확인해 보세요.", ids


def briefing_pool(scope, session):
    if scope == BriefingThread.Scope.ALL:
        return AuctionLot.objects.all()
    ids = winner_ids(session) if session else set()
    if len(ids) < RECOMMENDATION_MIN:
        return None
    return AuctionLot.objects.filter(pk__in=ids)


def find_thread(token, session, scope):
    if not token:
        return None
    if not session:
        raise Http404
    try:
        token = UUID(token)
    except ValueError as error:
        raise Http404 from error
    return get_object_or_404(BriefingThread, token=token, session_id=session, scope=scope)


def ordered_lots(pool, ids, limit=VISIBLE_RESULTS):
    found = pool.in_bulk(ids[:limit], field_name="public_id")
    return [found[key] for key in ids[:limit] if key in found]


def briefing_page(request, scope, session, thread, pool, form, status=200):
    recent = BriefingThread.objects.filter(session_id=session, scope=scope).order_by("-updated_at", "-pk")[:MAX_THREADS]
    messages = []
    preview = []
    if pool is not None:
        if thread:
            exchanges = list(thread.exchanges.order_by("-pk")[:MAX_EXCHANGES])
            messages = [(item, ordered_lots(pool, item.lot_ids)) for item in reversed(exchanges)]
        elif scope == BriefingThread.Scope.ALL:
            preview = ordered_lots(pool, request.GET.getlist("lot"), 2)
    return render(request, "auctions/briefing.html", {
        "active": "briefing", "scope": scope, "thread": thread, "recent": recent,
        "messages": messages, "form": form, "eligible": pool is not None, "preview": preview,
    }, status=status)


@require_http_methods(["GET", "HEAD", "POST"])
def briefing(request):
    submitting = request.method == "POST"
    data = request.POST if submitting else request.GET
    scope = data.get("scope", BriefingThread.Scope.ALL)
    if scope not in BriefingThread.Scope.values:
        return HttpResponseBadRequest("브리핑 범위를 확인해 주세요.")
    session = browser_session(request)
    thread = find_thread(data.get("thread"), session, scope)
    pool = briefing_pool(scope, session)
    form = BriefingForm(data if submitting else None)
    if not submitting:
        return briefing_page(request, scope, session, thread, pool, form)
    if pool is None or not form.is_valid():
        return briefing_page(request, scope, session, thread, pool, form, status=400)

    question = form.cleaned_data["question"]
    with transaction.atomic():
        locked_session = lock_browser_session(request)
        pool = briefing_pool(scope, locked_session.pk)
        if pool is None:
            return briefing_page(request, scope, locked_session.pk, None, None, form, status=400)
        thread = find_thread(data.get("thread"), locked_session.pk, scope)
        if thread is None:
            thread = BriefingThread.objects.create(session=locked_session, scope=scope, title=question[:80])
        prior = thread.exchanges.order_by("-pk").first()
        preview = ordered_lots(pool, data.getlist("lot"), 2) if scope == BriefingThread.Scope.ALL else []
        previous = prior.lot_ids if prior else [lot.public_id for lot in preview]
        answer, ids = answer_query(question, pool, previous)
        BriefingExchange.objects.create(thread=thread, question=question, answer=answer, lot_ids=ids)
        thread.save(update_fields=["updated_at"])
        stale = list(thread.exchanges.order_by("-pk").values_list("pk", flat=True)[MAX_EXCHANGES:])
        BriefingExchange.objects.filter(pk__in=stale).delete()
        threads = BriefingThread.objects.filter(session=locked_session)
        expired = list(threads.order_by("-updated_at", "-pk").values_list("pk", flat=True)[MAX_THREADS:])
        threads.filter(pk__in=expired).delete()
    return redirect(reverse("auctions:briefing") + "?" + urlencode({"scope": scope, "thread": thread.token}))
