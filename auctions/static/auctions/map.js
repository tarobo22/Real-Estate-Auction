(() => {
  const app = document.getElementById("map-app");
  if (!app) return;

  const element = (id) => document.getElementById(id);
  const svg = element("fallback-map");
  const kakaoElement = element("kakao-map");
  const boundaryLayer = element("boundary-layer");
  const pinLayer = element("pin-layer");
  const rows = element("map-rows");
  const list = element("map-list");
  const search = element("map-search");
  const all = element("map-all");
  const clearRange = element("map-clear-range");
  const hint = element("map-hint");
  const status = element("map-status");
  const dialog = element("lot-dialog");
  const fragment = element("lot-fragment");
  const width = 640;
  const height = 440;
  const radius = 6371.0088;
  const radians = Math.PI / 180;
  const searchHint = "가로·세로 각각 30km 이내로 확대하면 이 지도에서 검색할 수 있습니다.";
  const defaultBounds = { west: 126.16, south: 37.05, east: 127.75, north: 38.05 };
  let pins = JSON.parse(element("initial-pins").textContent);
  let features = [];
  let bounds = fit(pins);
  const initialBounds = { ...bounds };
  let kakao = null;
  let overlays = [];
  let activeRequest = null;
  let detailRequest = null;
  let opener = null;
  let openingMarker = "";
  let dragged = null;
  let scheduled = false;
  let truncated = status.textContent.includes("100건");
  const mobile = matchMedia("(max-width: 720px)");
  if (mobile.matches) list.open = false;
  const summary = list.querySelector("summary");
  let touchStart = null;
  summary.addEventListener("touchstart", (event) => { touchStart = event.changedTouches[0].clientY; }, { passive: true });
  summary.addEventListener("touchend", (event) => {
    if (mobile.matches && touchStart !== null && touchStart - event.changedTouches[0].clientY > 25) list.open = true;
    touchStart = null;
  }, { passive: true });

  function fit(points) {
    if (!points.length) return { ...defaultBounds };
    const longitudes = points.map((pin) => pin.longitude);
    const latitudes = points.map((pin) => pin.latitude);
    const lon = (Math.min(...longitudes) + Math.max(...longitudes)) / 2;
    const lat = (Math.min(...latitudes) + Math.max(...latitudes)) / 2;
    const span = Math.max(.11, (Math.max(...longitudes) - Math.min(...longitudes)) * .65,
      (Math.max(...latitudes) - Math.min(...latitudes)) * .85);
    return { west: lon - span, east: lon + span, south: lat - span * .7, north: lat + span * .7 };
  }

  function viewBounds() {
    if (!kakao) return bounds;
    const viewport = kakao.getBounds();
    const sw = viewport.getSouthWest();
    const ne = viewport.getNorthEast();
    return { west: sw.getLng(), south: sw.getLat(), east: ne.getLng(), north: ne.getLat() };
  }

  function validBounds(box) {
    const wide = radius * radians * (box.east - box.west) * Math.cos(radians * (box.south + box.north) / 2);
    const tall = radius * radians * (box.north - box.south);
    return wide > 0 && tall > 0 && Math.max(wide, tall) <= 30 + 1e-9;
  }

  function point(x, y) {
    return [(x - bounds.west) * width / (bounds.east - bounds.west),
      (bounds.north - y) * height / (bounds.north - bounds.south)];
  }

  function svgNode(tag, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  }

  function renderBoundaries() {
    const paths = features.map(({ geometry, properties }) => {
      const polygons = geometry.type === "MultiPolygon" ? geometry.coordinates : [geometry.coordinates];
      const d = polygons.flatMap((rings) => rings.map((ring) => {
        const coordinates = ring.map(([lon, lat]) => point(lon, lat).map((n) => n.toFixed(1)).join(","));
        return "M" + coordinates.join("L") + "Z";
      })).join("");
      return svgNode("path", { d, class: properties.level === 2 ? "boundary district" : "boundary",
        "fill-rule": "evenodd" });
    });
    boundaryLayer.replaceChildren(...paths);
  }

  function markerGroups(project, maxX, maxY) {
    const groups = new Map();
    for (const pin of pins) {
      const [x, y] = project(pin.longitude, pin.latitude);
      if (x < 0 || x > maxX || y < 0 || y > maxY) continue;
      const cell = Math.round(x / 64) + ":" + Math.round(y / 35);
      if (!groups.has(cell)) groups.set(cell, { x, y, items: [] });
      groups.get(cell).items.push(pin);
    }
    return groups.values();
  }

  function markerLabel(items) {
    return items.length > 1 ? items.length + "건" : items[0].display_price;
  }

  function markerName(items) {
    return items.length > 1 ? "묶인 매물 " + items.length + "건" : items[0].name + " " + items[0].price_label + " " + items[0].display_price;
  }

  function showRows(ids = null) {
    const nodes = rows.querySelectorAll("[data-lot-id]");
    let count = 0;
    for (const row of nodes) {
      row.hidden = ids !== null && !ids.has(row.dataset.lotId);
      if (!row.hidden) count += 1;
    }
    all.hidden = ids === null;
    status.textContent = count + "건" + (truncated && ids === null ? " · 100건까지만 표시" : "");
  }

  function markerAction(items, trigger) {
    if (items.length === 1) {
      const link = rows.querySelector('[data-lot-id="' + CSS.escape(items[0].id) + '"] a');
      openDetail(link?.href || items[0].url, trigger);
    } else {
      showRows(new Set(items.map((pin) => pin.id)));
      list.open = true;
      rows.querySelector("[data-lot-id]:not([hidden]) a")?.focus();
    }
  }

  function renderFallbackPins() {
    const markers = [];
    for (const { x, y, items } of markerGroups(point, width, height)) {
      const label = markerLabel(items);
      const size = Math.max(35, label.length * 8 + 14);
      const node = svgNode("g", {
        class: "map-marker", role: "button", tabindex: 0, "aria-label": markerName(items),
        "data-marker-key": items[0].id,
        transform: "translate(" + x + " " + y + ")",
      });
      node.append(svgNode("rect", { x: -size / 2, y: -13, width: size, height: 25, rx: 7 }));
      const text = svgNode("text", { "text-anchor": "middle", y: 4 });
      text.textContent = label;
      node.append(text);
      node.addEventListener("click", () => markerAction(items, node));
      node.addEventListener("keydown", (event) => {
        if (!["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        markerAction(items, node);
      });
      markers.push(node);
    }
    pinLayer.replaceChildren(...markers);
  }

  function renderKakaoPins() {
    const maps = window.kakao.maps;
    for (const overlay of overlays) overlay.setMap(null);
    overlays = [];
    const projection = kakao.getProjection();
    const project = (lon, lat) => {
      const projected = projection.containerPointFromCoords(new maps.LatLng(lat, lon));
      return [projected.x, projected.y];
    };
    for (const { items } of markerGroups(project, kakaoElement.clientWidth, kakaoElement.clientHeight)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "map-pin";
      button.dataset.markerKey = items[0].id;
      button.textContent = markerLabel(items);
      button.setAttribute("aria-label", markerName(items));
      button.addEventListener("click", () => markerAction(items, button));
      const position = new maps.LatLng(items[0].latitude, items[0].longitude);
      overlays.push(new maps.CustomOverlay({ map: kakao, position, content: button, yAnchor: .5 }));
    }
  }

  function updateMap() {
    const valid = validBounds(viewBounds());
    search.disabled = !valid || activeRequest !== null;
    hint.textContent = valid ? "지도를 움직인 뒤 검색 버튼을 누르면 목록과 핀이 함께 갱신됩니다." : searchHint;
    if (kakao) renderKakaoPins();
    else {
      renderBoundaries();
      renderFallbackPins();
    }
  }

  function scheduleMap() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      updateMap();
    });
  }

  function shift(x, y) {
    const dx = (bounds.east - bounds.west) * x;
    const dy = (bounds.north - bounds.south) * y;
    if (bounds.west + dx < -180 || bounds.east + dx > 180 || bounds.south + dy < -90 || bounds.north + dy > 90) return;
    bounds = { west: bounds.west + dx, east: bounds.east + dx, south: bounds.south + dy, north: bounds.north + dy };
    scheduleMap();
  }

  function zoom(inward) {
    if (kakao) {
      kakao.setLevel(kakao.getLevel() + (inward ? -1 : 1), { animate: false });
      return;
    }
    const factor = inward ? .58 : 1 / .58;
    const lon = (bounds.west + bounds.east) / 2;
    const lat = (bounds.south + bounds.north) / 2;
    const dx = (bounds.east - bounds.west) / 2 * factor;
    const dy = (bounds.north - bounds.south) / 2 * factor;
    if (dx < .001 || dx > 4 || lon - dx < -180 || lon + dx > 180 || lat - dy < -90 || lat + dy > 90) return;
    bounds = { west: lon - dx, east: lon + dx, south: lat - dy, north: lat + dy };
    scheduleMap();
  }

  function setKakaoBounds(box) {
    const maps = window.kakao.maps;
    kakao.setBounds(new maps.LatLngBounds(new maps.LatLng(box.south, box.west), new maps.LatLng(box.north, box.east)));
  }

  element("zoom-in").addEventListener("click", () => zoom(true));
  element("zoom-out").addEventListener("click", () => zoom(false));
  element("zoom-reset").addEventListener("click", () => {
    if (kakao) setKakaoBounds(initialBounds);
    else bounds = { ...initialBounds };
    scheduleMap();
  });
  all.addEventListener("click", () => showRows());
  svg.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest(".map-marker")) return;
    svg.setPointerCapture(event.pointerId);
    dragged = { x: event.clientX, y: event.clientY };
  });
  svg.addEventListener("pointermove", (event) => {
    if (!dragged) return;
    const rect = svg.getBoundingClientRect();
    shift((dragged.x - event.clientX) / rect.width, (event.clientY - dragged.y) / rect.height);
    dragged = { x: event.clientX, y: event.clientY };
  });
  svg.addEventListener("lostpointercapture", () => { dragged = null; });
  svg.addEventListener("keydown", (event) => {
    if (event.target !== svg) return;
    const offsets = { ArrowLeft: [-.12, 0], ArrowRight: [.12, 0], ArrowUp: [0, .12], ArrowDown: [0, -.12] };
    if (!(event.key in offsets)) return;
    event.preventDefault();
    shift(...offsets[event.key]);
  });

  search.addEventListener("click", async () => {
    const box = viewBounds();
    if (!validBounds(box)) return;
    activeRequest?.abort();
    const controller = new AbortController();
    activeRequest = controller;
    search.disabled = true;
    status.textContent = "이 지도에서 물건을 찾는 중입니다.";
    try {
      const url = new URL(app.dataset.api, location.href);
      url.search = location.search;
      for (const [key, value] of Object.entries(box)) url.searchParams.set(key, value);
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error("map search");
      const data = await response.json();
      if (activeRequest !== controller) return;
      pins = data.lots;
      truncated = data.truncated;
      rows.innerHTML = data.list_html;
      showRows();
      clearRange.hidden = false;
      if (mobile.matches) list.open = true;
    } catch (error) {
      if (error.name !== "AbortError") status.textContent = "검색할 수 없습니다. 다시 시도해 주세요.";
    } finally {
      if (activeRequest === controller) {
        activeRequest = null;
        scheduleMap();
      }
    }
  });

  async function openDetail(href, trigger) {
    if (!dialog.showModal) {
      location.assign(href);
      return;
    }
    detailRequest?.abort();
    const controller = new AbortController();
    detailRequest = controller;
    opener = trigger;
    openingMarker = trigger.dataset.markerKey || "";
    fragment.textContent = "상세를 불러오는 중입니다.";
    if (!dialog.open) dialog.showModal();
    try {
      const url = new URL(href, location.href);
      url.searchParams.set("fragment", "1");
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error("lot detail");
      const content = await response.text();
      if (detailRequest === controller && dialog.open) fragment.innerHTML = content;
    } catch (error) {
      if (error.name === "AbortError" || !dialog.open) return;
      const link = document.createElement("a");
      link.href = href;
      link.textContent = "상세 화면 열기";
      fragment.replaceChildren(link);
    }
  }

  rows.addEventListener("click", (event) => {
    const link = event.target.closest(".map-lot-link");
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    openDetail(link.href, link);
  });
  dialog.addEventListener("close", () => {
    detailRequest?.abort();
    detailRequest = null;
    if (opener?.isConnected) opener.focus({ preventScroll: true });
    else {
      const current = openingMarker && app.querySelector('[data-marker-key="' + CSS.escape(openingMarker) + '"]');
      (current || svg).focus({ preventScroll: true });
    }
    opener = null;
    openingMarker = "";
  });

  function enableKakao(key) {
    const script = document.createElement("script");
    const url = new URL("https://dapi.kakao.com/v2/maps/sdk.js");
    url.search = new URLSearchParams({ appkey: key, autoload: "false" });
    script.src = url;
    script.async = true;
    script.addEventListener("load", () => {
      const maps = window.kakao?.maps;
      if (!maps?.load) return;
      maps.load(() => {
        try {
          kakaoElement.hidden = false;
          kakao = new maps.Map(kakaoElement, { center: new maps.LatLng(37.5, 127), level: 9 });
          setKakaoBounds(bounds);
          maps.event.addListener(kakao, "idle", scheduleMap);
          svg.hidden = true;
          element("map-provider").textContent = "카카오맵";
          scheduleMap();
        } catch {
          kakao = null;
          kakaoElement.hidden = true;
          svg.hidden = false;
          scheduleMap();
        }
      });
    });
    document.head.append(script);
  }

  updateMap();
  fetch(app.dataset.boundaries).then((response) => {
    if (!response.ok) throw new Error("boundaries");
    return response.json();
  }).then((data) => {
    features = data.features;
    scheduleMap();
  }).catch(() => {
    if (!kakao) element("map-provider").textContent = "매물 위치 지도";
  });
  if (app.dataset.kakaoKey) enableKakao(app.dataset.kakaoKey);
})();
