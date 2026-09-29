"""구글맵 링크를 받아 My Maps 가져오기용 CSV에 장소(이름, 좌표)를 쌓는 CLI."""

import argparse
import csv
import html
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse

FIELDS = ["이름", "위도", "경도", "태그", "메모", "링크", "추가일"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
COORD = r"(-?\d{1,3}\.\d+)"


def fetch(url: str) -> tuple[str, str]:
    """리다이렉트를 따라가 (최종 URL, 페이지 HTML)을 반환한다."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ko"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        final = resp.geturl()
        body = resp.read().decode("utf-8", errors="replace")
    # EU 등에서는 동의 페이지로 튕기는데, 원래 주소가 continue 파라미터에 들어 있다.
    if urlparse(final).netloc.startswith("consent."):
        return fetch(parse_qs(urlparse(final).query).get("continue", [final])[0])
    return final, body


def parse_coords(url: str) -> tuple[float, float] | None:
    url = unquote_plus(url)
    # !3d{lat}!4d{lng}: 장소 핀의 실제 좌표. 가장 정확하므로 우선한다.
    m = re.findall(rf"!3d{COORD}!4d{COORD}", url)
    if m:
        lat, lng = m[-1]
        return float(lat), float(lng)
    # q=lat,lng / ll=lat,lng / query=lat,lng
    params = parse_qs(urlparse(url).query)
    for key in ("q", "query", "ll", "center"):
        for value in params.get(key, []):
            m = re.fullmatch(rf"\s*{COORD}\s*,\s*{COORD}\s*", value)
            if m:
                return float(m[1]), float(m[2])
    # @lat,lng,zoom: 화면 중심 좌표. 핀 좌표가 없을 때만 쓴다.
    m = re.search(rf"@{COORD},{COORD}", url)
    if m:
        return float(m[1]), float(m[2])
    return None


def parse_coords_from_html(page: str) -> tuple[float, float] | None:
    """모바일 공유 링크처럼 URL에 좌표가 없을 때, 페이지 HTML에 박힌 좌표를 찾는다."""
    # 미리보기 이미지(staticmap)의 center=lat,lng
    m = re.search(rf"staticmap\?center={COORD}(?:%2C|,){COORD}", page)
    if m:
        return float(m[1]), float(m[2])
    # APP_INITIALIZATION_STATE=[[[zoom,lng,lat] (경도가 먼저)
    m = re.search(rf"APP_INITIALIZATION_STATE=\[\[\[-?[\d.]+,{COORD},{COORD}\]", page)
    if m:
        return float(m[2]), float(m[1])
    return None


def parse_name_from_html(page: str) -> str | None:
    m = re.search(r'<meta content="([^"]*)" (?:itemprop="name"|property="og:title")', page) or \
        re.search(r'<meta (?:itemprop="name"|property="og:title") content="([^"]*)"', page)
    if not m:
        return None
    # "이름 · 주소" 형태로 오므로 앞부분만 쓴다.
    name = html.unescape(m[1]).split(" · ")[0].strip()
    return name if name and name != "Google Maps" else None


def parse_name(url: str) -> str | None:
    parsed = urlparse(url)
    m = re.search(r"/maps/place/([^/]+)", parsed.path)
    if m:
        return unquote_plus(m[1])
    for value in parse_qs(parsed.query).get("q", []):
        if not re.fullmatch(rf"\s*{COORD}\s*,\s*{COORD}\s*", value):
            return value.split(",")[0].strip()
    return None


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_row(path: Path, row: dict) -> None:
    new_file = not path.exists()
    with path.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def is_duplicate(rows: list[dict], lat: float, lng: float) -> dict | None:
    for row in rows:
        try:
            if abs(float(row["위도"]) - lat) < 1e-5 and abs(float(row["경도"]) - lng) < 1e-5:
                return row
        except (KeyError, ValueError):
            continue
    return None


def add(url: str, csv_path: Path, name: str | None, note: str, debug: bool = False) -> bool:
    final, page = url, ""
    coords = parse_coords(url)
    if coords is None:
        final, page = fetch(url)
        coords = parse_coords(final) or parse_coords_from_html(page)
        if debug:
            Path("debug.html").write_text(page, encoding="utf-8")
            print(f"[디버그] 최종 URL: {final}\n[디버그] HTML을 debug.html에 저장했습니다.")
    if coords is None:
        print(
            f"[실패] 좌표를 찾지 못했습니다: {url}\n"
            f"  최종 URL: {final}\n"
            "  PC 브라우저에서 링크를 열고, 지도가 로드된 뒤 주소창의 URL을 복사해 다시 넣어 주세요.\n"
            "  (--debug 옵션으로 실행하면 받은 HTML을 debug.html에 저장합니다.)",
            file=sys.stderr,
        )
        return False
    lat, lng = coords
    name = name or parse_name_from_html(page) or parse_name(final) or f"{lat:.5f},{lng:.5f}"

    dup = is_duplicate(load_rows(csv_path), lat, lng)
    if dup:
        print(f"[건너뜀] 이미 있는 장소입니다: {dup['이름']} ({lat}, {lng})")
        return True

    append_row(csv_path, {
        "이름": name, "위도": lat, "경도": lng, "태그": "", "메모": note,
        "링크": url, "추가일": date.today().isoformat(),
    })
    print(f"[추가] {name} ({lat}, {lng})")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="구글맵 링크를 My Maps용 CSV에 추가합니다.")
    parser.add_argument("urls", nargs="+", help="구글맵 링크 (여러 개 가능)")
    parser.add_argument("--csv", type=Path, default=Path("places.csv"), help="저장할 CSV (기본: places.csv)")
    parser.add_argument("--name", help="장소 이름 직접 지정 (링크 1개일 때만)")
    parser.add_argument("--note", default="", help="메모")
    parser.add_argument("--debug", action="store_true", help="받은 페이지 HTML을 debug.html에 저장")
    args = parser.parse_args(argv)

    if args.name and len(args.urls) > 1:
        parser.error("--name은 링크가 1개일 때만 쓸 수 있습니다.")

    ok = True
    for url in args.urls:
        try:
            ok &= add(url, args.csv, args.name, args.note, args.debug)
        except OSError as e:
            print(f"[실패] 링크를 열 수 없습니다: {url} ({e})", file=sys.stderr)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
