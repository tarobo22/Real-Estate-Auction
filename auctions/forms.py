import math

from django import forms

from .models import LotUse, Region


BUDGET_CHOICES = [("", "제한 없음"), *[(str(amount * 10_000), f"{amount}억 원") for amount in (3, 5, 7, 8, 10, 12, 20)]]
DAY_CHOICES = [("", "전체 기간"), *[(str(days), f"{days}일 이내") for days in (7, 14, 30)]]
PRICE_BANDS = {"lt3": (None, 3), "3-5": (3, 5), "5-10": (5, 10), "gte10": (10, None)}
RATE_BANDS = {"lt50": (None, 50), "50-80": (50, 80), "80-100": (80, 100), "gte100": (100, None)}


class LotFilter(forms.Form):
    q = forms.CharField(required=False, max_length=120, label="검색어", widget=forms.TextInput(
        attrs={"placeholder": "지역·단지명·사건번호 검색"},
    ))
    region = forms.ChoiceField(required=False, choices=[("", "전체 지역"), *Region.choices], label="지역")
    use = forms.ChoiceField(required=False, choices=[("", "전체 용도"), *LotUse.choices], label="용도")
    budget = forms.IntegerField(
        required=False, min_value=0, max_value=10**10, label="최대 가격 (만원)",
        widget=forms.Select(choices=BUDGET_CHOICES),
    )
    kind = forms.ChoiceField(
        required=False, choices=[("upcoming", "입찰 예정"), ("sold", "낙찰 사례"), ("all", "전체")],
        label="상태",
    )
    days = forms.IntegerField(
        required=False, min_value=1, max_value=365, label="예정 기일",
        widget=forms.Select(choices=DAY_CHOICES),
    )
    sale_date = forms.DateField(required=False, label="낙찰일", input_formats=["%Y-%m-%d"])

    def __init__(self, *args, sale_dates=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sale_date"].widget = forms.Select(choices=[
            ("", "전체 낙찰일"), *((day.isoformat(), day.isoformat()) for day in sale_dates),
        ])
        if self.data.get("kind") != "sold":
            self.fields["sale_date"].disabled = True
        for name, suffix in (("budget", "만 원"), ("days", "일 이내")):
            value = self.data.get(name, "")
            widget = self.fields[name].widget
            if len(value) <= 11 and value.isascii() and value.isdecimal() and value not in dict(widget.choices):
                widget.choices = [*widget.choices, (value, f"{int(value):,}{suffix}")]

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


class ResultsFilter(forms.Form):
    STATUS_CHOICES = [("upcoming", "진행중"), ("pending", "낙찰대기"), ("sold", "완료"), ("undated", "기일 미상")]
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False)
    region = forms.ChoiceField(choices=[("", "전체 지역"), *Region.choices], required=False, label="지역")
    use = forms.ChoiceField(choices=[("", "전체 용도"), *LotUse.choices], required=False, label="용도")
    price_band = forms.ChoiceField(required=False, label="가격대", choices=[
        ("", "전체 가격"), ("lt3", "3억 미만"), ("3-5", "3억 이상 5억 미만"),
        ("5-10", "5억 이상 10억 미만"), ("gte10", "10억 이상"),
    ])
    rate_band = forms.ChoiceField(required=False, label="낙찰가율", choices=[
        ("", "전체 낙찰가율"), ("lt50", "50% 미만"), ("50-80", "50% 이상 80% 미만"),
        ("80-100", "80% 이상 100% 미만"), ("gte100", "100% 이상"),
    ])
    min_price = forms.DecimalField(required=False, min_value=0, max_digits=14, decimal_places=4, label="최소 가격 (만원)")
    max_price = forms.DecimalField(required=False, min_value=0, max_digits=14, decimal_places=4, label="최대 가격 (만원)")
    min_rate = forms.DecimalField(required=False, min_value=0, max_digits=9, decimal_places=2, label="최소 낙찰가율 (%)")
    max_rate = forms.DecimalField(required=False, min_value=0, max_digits=9, decimal_places=2, label="최대 낙찰가율 (%)")
    sort = forms.ChoiceField(required=False, choices=[
        ("", "기일·낙찰일"), ("price-low", "낮은 가격"), ("price-high", "높은 가격"),
    ], label="정렬")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.data.get("status") != "sold":
            for name in ("min_rate", "max_rate", "rate_band"):
                self.fields[name].disabled = True

    def clean_status(self):
        return self.cleaned_data["status"] or "upcoming"

    def clean(self):
        values = super().clean()
        for low, high in (("min_price", "max_price"), ("min_rate", "max_rate")):
            if values.get(low) is not None and values.get(high) is not None and values[low] > values[high]:
                self.add_error(high, "최댓값은 최솟값 이상이어야 합니다.")
        return values


class BriefingForm(forms.Form):
    question = forms.CharField(
        max_length=240, label="질문",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "예: 인천 아파트 5억 이하 찾아줘"}),
    )
