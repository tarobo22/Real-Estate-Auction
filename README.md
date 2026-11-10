# 입찰랩 · Django MVT

수도권 법원경매 공개 사례를 검색하고 지도, 상세, 낙찰 화면에서 확인하는 Django 앱입니다. 시드 데이터 기준일은 2026년 11월 10일입니다.

## Lightsail에서 실행

x86_64 Lightsail Linux 인스턴스에 Docker Engine과 Compose를 준비합니다. 저장소의 `auction-lab/`에서 실행합니다.

서버에만 보관하는 `.env`에 아래 변수를 설정합니다. 비밀번호와 Django 서명 키에는 서로 다른 값을 사용합니다.

```dotenv
AUCTION_DB_ADMIN_PASSWORD=
AUCTION_DB_PASSWORD=
AUCTION_SECRET_KEY=
AUCTION_ALLOWED_HOSTS=localhost,127.0.0.1
AUCTION_PORT=8000
AUCTION_HTTPS=0
# AUCTION_KAKAO_MAP_JS_KEY=
```

```sh
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_auctions
docker compose up -d
```

웹 컨테이너는 호스트의 루프백 주소에 연결되며 PostgreSQL은 Compose 내부 네트워크에 있습니다. 도메인을 붙일 때는 HTTPS 리버스 프록시가 `127.0.0.1:8000`을 향하도록 설정하고, 프록시가 `Host`와 `X-Forwarded-Proto`를 직접 설정하도록 구성합니다. `AUCTION_ALLOWED_HOSTS`에는 실제 도메인을 추가하고 `AUCTION_HTTPS=1`을 설정합니다. Lightsail 방화벽은 리버스 프록시의 HTTP·HTTPS 포트만 공개합니다.

최초 DB 초기화에서 PostGIS 확장과 애플리케이션 역할을 준비합니다. DB 볼륨을 재사용하면서 비밀번호를 교체할 때는 PostgreSQL 역할의 비밀번호도 함께 변경해야 합니다. `pg_dump` 백업은 인스턴스 외부에 보관하고 복원을 검증합니다.

카카오맵을 쓰려면 서비스 도메인에 허용된 JavaScript SDK 키를 지정합니다. 키를 비워 두면 행정구역 지도로 동작합니다.

## 테스트

```sh
docker compose -p auction-lab-tdd -f compose.test.yaml run --build --rm test
docker compose -p auction-lab-tdd -f compose.test.yaml down
```

테스트는 외부 포트를 열지 않는 별도 PostgreSQL 17·PostGIS 3.6 인스턴스와 임시 볼륨을 사용합니다. 이 테스트 구성은 운영에 사용하지 않습니다.

시드까지 적재한 로컬 서버를 켜고 Chromium으로 주요 흐름을 검증할 수 있습니다.

```sh
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
AUCTION_BROWSER_URL=http://127.0.0.1:8000 python -m unittest discover -s browser_tests -v
```

브라우저 테스트는 테스트용 인스턴스에서 실행합니다. 확인 범위는 홈 검색과 지도·장바구니, 모바일 목록 복귀, VS 추천과 브리핑, 문의 문안의 클립보드 상태입니다.

## 공간 데이터와 출처

매물의 공개 ID는 기존 시연 데이터와 같습니다. 가져온 경·위도에서 WGS84 포인트를 생성하고 GiST 인덱스로 지도 범위를 조회합니다. 좌표 미수록 물건은 초기 목록에 표시되며 핀과 범위 검색에서는 빠집니다.

공개 사례와 예시 사진, 입지 보고서는 입찰랩 전달본에서 옮겼습니다. 경계는 geoBoundaries gbOpen, Natural Earth, citypopulation.de의 자료를 간소화한 것입니다. 상세 출처와 변경 정보는 경계 데이터의 `sources`와 `processing`에 기록되어 있습니다. Pretendard 폰트는 동봉한 라이선스를 따릅니다.
