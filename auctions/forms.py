import math

from django import forms

from .models import LotUse, Region


class LotFilter(forms.Form):
    q = forms.CharField(required=False, max_length=120, label="검색어", widget=forms.TextInput(
        attrs={"placeholder": "지역·단지명·사건번호 검색"},
    ))
    region = forms.ChoiceField(required=False, choices=[("", "전체 지역"), *Region.choices], label="지역")
    use = forms.ChoiceField(required=False, choices=[("", "전체 용도"), *LotUse.choices], label="용도")
    budget = forms.IntegerField(required=False, min_value=0, max_value=10**10, label="최대 가격 (만원)")
    kind = forms.ChoiceField(
        required=False, choices=[("upcoming", "입찰 예정"), ("sold", "낙찰 사례"), ("all", "전체")],
        label="상태",
    )
    days = forms.IntegerField(required=False, min_value=1, max_value=365, label="기간 (일)")

    def clean_kind(self):
        return self.cleaned_data["kind"] or "upcoming"


EARTH_RADIUS_KM = 6371.0088
MAX_MAP_KM = 30


def extent_km(west, south, east, north):
    mid_latitude = math.radians((south + north) / 2)
    return (
        EARTH_RADIUS_KM * math.radians(east - west) * math.cos(mid_latitude),
        EARTH_RADIUS_KM * math.radians(north - south),
    )


class BoundsForm(forms.Form):
    west = forms.FloatField(min_value=-180, max_value=180)
    south = forms.FloatField(min_value=-90, max_value=90)
    east = forms.FloatField(min_value=-180, max_value=180)
    north = forms.FloatField(min_value=-90, max_value=90)

    def clean(self):
        values = super().clean()
        if self.errors:
            return values
        west, south, east, north = (values[key] for key in ("west", "south", "east", "north"))
        if west >= east or south >= north:
            raise forms.ValidationError("서쪽·남쪽 좌표가 동쪽·북쪽보다 작아야 합니다.", code="order")
        if max(extent_km(west, south, east, north)) > MAX_MAP_KM + 1e-9:
            raise forms.ValidationError("가로·세로 각각 30km 이하로 지도를 확대해 주세요.", code="extent")
        values["bbox"] = west, south, east, north
        return values
