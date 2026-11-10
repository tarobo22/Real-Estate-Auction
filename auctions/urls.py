from django.urls import path
from django.views.generic import RedirectView, TemplateView

from . import briefing, cart, comparison, results, views


app_name = "auctions"
urlpatterns = [
    path("", views.home, name="home"),
    path("about.html", RedirectView.as_view(pattern_name="auctions:home"), name="about"),
    path("map/", views.listing_map, name="map"),
    path("api/map/lots/", views.map_api, name="map-api"),
    path("lots/<slug:public_id>/", views.lot_detail, name="detail"),
    path("results/", results.results, name="results"),
    path("cart/", cart.cart, name="cart"),
    path("vs/", comparison.versus, name="vs"),
    path("vs/inquiry/", comparison.inquiry, name="inquiry"),
    path("briefing/", briefing.briefing, name="briefing"),
    path("location-data-report.html", TemplateView.as_view(template_name="auctions/location-data-report.html"), name="location-report"),
]
