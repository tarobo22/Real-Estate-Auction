from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .models import AuctionLot, CartItem
from .sessions import browser_session, lock_browser_session


def cart_context(request):
    if not hasattr(request, "auction_cart"):
        session = browser_session(request)
        request.auction_cart = list(
            CartItem.objects.filter(session_id=session).select_related("lot").order_by("-pk")
        ) if session else []
    rows = request.auction_cart
    return {"cart_rows": rows, "cart_ids": {row.lot.public_id for row in rows}, "cart_count": len(rows)}


@require_http_methods(["GET", "HEAD", "POST"])
def cart(request):
    if request.method != "POST":
        return render(request, "auctions/cart.html")
    action = request.POST.get("action")
    if action not in {"add", "remove", "clear"}:
        return HttpResponseBadRequest("장바구니 동작을 확인해 주세요.")
    lot = None if action == "clear" else get_object_or_404(AuctionLot, public_id=request.POST.get("lot", ""))
    with transaction.atomic():
        session = lock_browser_session(request)
        items = CartItem.objects.filter(session=session)
        if action == "add":
            CartItem.objects.get_or_create(session=session, lot=lot)
        elif action == "remove":
            items.filter(lot=lot).delete()
        else:
            items.delete()
        context = cart_context(request)
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({
            "ids": sorted(context["cart_ids"]), "count": context["cart_count"],
            "html": render_to_string("auctions/_cart_contents.html", context, request=request),
        })
    target = request.POST.get("return_to", "")
    if target.startswith("/") and url_has_allowed_host_and_scheme(target, allowed_hosts=set()):
        return redirect(target)
    return redirect(reverse("auctions:cart"))
