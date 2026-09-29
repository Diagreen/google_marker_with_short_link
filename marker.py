"""구글맵 링크를 받아 My Maps 가져오기용 CSV에 장소(이름, 좌표)를 쌓는 CLI.

휴대폰에서 공유한 링크(maps.app.goo.gl)는 풀어도 좌표가 없고, 좌표는 페이지의
자바스크립트가 장소를 불러온 뒤에야 주소창 URL에 붙는다. 그래서 좌표가 없는 링크는
Playwright로 화면 없는 크롬을 띄워 연 다음 주소창 URL을 읽는다.
"""

import argparse
import csv
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse

FIELDS = ["이름", "위도", "경도", "태그", "메모", "링크", "추가일"]
COORD = r"(-?\d{1,3}\.\d+)"
PIN = rf"!3d{COORD}!4d{COORD}"


class BrowserResolver:
    """화면 없는 크롬으로 링크를 열어, 장소 핀 좌표가 붙은 최종 URL을 얻는다.

    브라우저 실행이 느리므로 with 블록 안에서 여러 링크에 재사용한다.
    """

    def __init__(self, timeout: float = 20, headless: bool = True):
        self.timeout = timeout
        self.headless = headless
        self._pw = self._browser = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _page(self):
        if self._browser is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                raise RuntimeError(
                    "Playwright가 설치되어 있지 않습니다. "
                    "`pip install playwright` 후 `playwright install chromium`을 실행하세요."
                ) from None
            self._pw = sync_playwright().start()
            try:
                self._browser = self._pw.chromium.launch(headless=self.headless)
            except Exception:
                # 정리하지 않으면 다음 링크에서 Playwright를 다시 시작하다 엉뚱한 에러가 난다.
                self._pw.stop()
                self._pw = None
                raise
        return self._browser.new_page(locale="ko-KR")

    def resolve(self, url: str, screenshot: Path | None = None) -> str:
        """링크를 열고, 주소창에 핀 좌표(!3d…!4d…)가 붙을 때까지 기다린 뒤 그 URL을 반환한다.

        제한 시간 안에 핀 좌표가 안 붙으면 그 시점의 URL을 그대로 반환한다.
        화면 중심 좌표(@lat,lng)는 장소가 로드되기 전 기본 위치일 수 있어 기다리는 조건에서 뺐다.
        """
        page = self._page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            deadline = time.monotonic() + self.timeout
            while not re.search(PIN, unquote_plus(page.url)) and time.monotonic() < deadline:
                page.wait_for_timeout(250)
            if screenshot:
                page.screenshot(path=str(screenshot))
            return page.url
        finally:
            page.close()


def parse_coords(url: str) -> tuple[float, float] | None:
    url = unquote_plus(url)
    # !3d{lat}!4d{lng}: 장소 핀의 실제 좌표. 가장 정확하므로 우선한다.
    m = re.findall(PIN, url)
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
    # @lat,lng(화면 중심)는 장소 위치가 아닐 수 있어 쓰지 않는다.
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
        resolver: BrowserResolver | None = None, debug: bool = False) -> tuple[bool, str]:
    """링크 하나를 CSV에 추가하고 (성공 여부, 결과 메시지)를 반환한다."""
    final, log = url, ""
    coords = parse_coords(url)
    # 브라우저 주소창에서 복사한 URL에는 핀 좌표가 이미 있으므로 브라우저를 띄우지 않는다.
    if coords is None:
        try:
            if resolver:
                final = resolver.resolve(url, Path("debug.png") if debug else None)
            else:
                with BrowserResolver() as r:
                    final = r.resolve(url, Path("debug.png") if debug else None)
        except Exception as e:  # Playwright 미설치, 네트워크 오류, 타임아웃 등
            return False, f"[실패] 링크를 열 수 없습니다: {url} ({e})"
        if debug:
            log = f"[디버그] 최종 URL: {final}\n[디버그] 화면을 debug.png에 저장했습니다.\n"
        coords = parse_coords(final)
    if coords is None:
        return False, log + (
            f"[실패] 장소 좌표를 찾지 못했습니다: {url}\n"
            f"  최종 URL: {final}\n"
            "  PC 브라우저에서 링크를 열고, 지도가 로드된 뒤 주소창의 URL을 복사해 다시 넣어 주세요.\n"
            "  (--debug 옵션으로 실행하면 브라우저 화면을 debug.png에 저장합니다.)"
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
    parser.add_argument("--debug", action="store_true", help="최종 URL 출력, 브라우저 화면을 debug.png에 저장")
    parser.add_argument("--show-browser", action="store_true", help="브라우저 창을 띄워서 실행 (문제 확인용)")
    args = parser.parse_args(argv)

    if args.name and len(args.urls) > 1:
        parser.error("--name은 링크가 1개일 때만 쓸 수 있습니다.")

    all_ok = True
    with BrowserResolver(headless=not args.show_browser) as resolver:
        for url in args.urls:
            ok, message = add(url, args.csv, args.name, args.note, args.tag, resolver, args.debug)
            print(message, file=sys.stdout if ok else sys.stderr)
            all_ok &= ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
