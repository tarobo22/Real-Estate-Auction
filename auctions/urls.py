from django.urls import path
from django.views.generic import RedirectView, TemplateView

from . import views


app_name = "auctions"
urlpatterns = [
    path("", views.home, name="home"),
    path("about.html", RedirectView.as_view(pattern_name="auctions:home"), name="about"),
    path("map/", views.listing_map, name="map"),
    path("api/map/lots/", views.map_api, name="map-api"),
    path("lots/<slug:public_id>/", views.lot_detail, name="detail"),
    path("location-data-report.html", TemplateView.as_view(template_name="auctions/location-data-report.html"), name="location-report"),
]
