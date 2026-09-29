"""구글맵 링크를 받아 My Maps 가져오기용 CSV에 장소(이름, 좌표)를 쌓는 CLI."""

import argparse
import csv
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


def add(url: str, csv_path: Path, name: str | None = None, note: str = "", tag: str = "",
        debug: bool = False) -> tuple[bool, str]:
    """링크 하나를 CSV에 추가하고 (성공 여부, 결과 메시지)를 반환한다."""
    final, page, log = url, "", ""
    coords = parse_coords(url)
    if coords is None:
        try:
            final, page = fetch(url)
        except OSError as e:
            return False, f"[실패] 링크를 열 수 없습니다: {url} ({e})"
        # 모바일 공유 링크는 좌표 없이 장소 ID만 담고 있다. 페이지 HTML의 좌표는 접속자 IP
        # 기준 위치라 쓰면 안 된다(실제로 전혀 다른 곳이 찍혔다).
        coords = parse_coords(final)
        if debug:
            Path("debug.html").write_text(page, encoding="utf-8")
            log = f"[디버그] 최종 URL: {final}\n[디버그] HTML을 debug.html에 저장했습니다.\n"
    if coords is None:
        return False, log + (
            f"[실패] 좌표를 찾지 못했습니다: {url}\n"
            f"  최종 URL: {final}\n"
            "  PC 브라우저에서 링크를 열고, 지도가 로드된 뒤 주소창의 URL을 복사해 다시 넣어 주세요.\n"
            "  (--debug 옵션으로 실행하면 받은 HTML을 debug.html에 저장합니다.)"
        )
    lat, lng = coords
    name = name or parse_name(final) or f"{lat:.5f},{lng:.5f}"

    dup = is_duplicate(load_rows(csv_path), lat, lng)
    if dup:
        return True, log + f"[건너뜀] 이미 있는 장소입니다: {dup['이름']} ({lat}, {lng})"

    append_row(csv_path, {
        "이름": name, "위도": lat, "경도": lng, "태그": tag, "메모": note,
        "링크": url, "추가일": date.today().isoformat(),
    })
    return True, log + f"[추가] {name} ({lat}, {lng})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="구글맵 링크를 My Maps용 CSV에 추가합니다.")
    parser.add_argument("urls", nargs="+", help="구글맵 링크 (여러 개 가능)")
    parser.add_argument("--csv", type=Path, default=Path("places.csv"), help="저장할 CSV (기본: places.csv)")
    parser.add_argument("--name", help="장소 이름 직접 지정 (링크 1개일 때만)")
    parser.add_argument("--note", default="", help="메모")
    parser.add_argument("--tag", default="", help="태그")
    parser.add_argument("--debug", action="store_true", help="받은 페이지 HTML을 debug.html에 저장")
    args = parser.parse_args(argv)

    if args.name and len(args.urls) > 1:
        parser.error("--name은 링크가 1개일 때만 쓸 수 있습니다.")

    all_ok = True
    for url in args.urls:
        ok, message = add(url, args.csv, args.name, args.note, args.tag, args.debug)
        print(message, file=sys.stdout if ok else sys.stderr)
        all_ok &= ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
