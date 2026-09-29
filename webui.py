"""marker.py를 브라우저에서 쓰기 위한 간이 웹 UI. 실행: python webui.py"""

import argparse
import threading
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import marker

CSV_PATH = Path("places.csv")
LOCK = threading.Lock()

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>구글맵 마커 추가</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 24px auto; padding: 0 16px; color: #222; }}
  textarea, input {{ width: 100%; box-sizing: border-box; padding: 8px; font: inherit; }}
  textarea {{ height: 90px; }}
  label {{ display: block; margin-top: 12px; font-weight: 600; }}
  .row {{ display: flex; gap: 12px; }}
  .row > div {{ flex: 1; }}
  button {{ margin-top: 12px; padding: 8px 20px; font: inherit; cursor: pointer; }}
  pre {{ background: #f4f4f4; padding: 12px; white-space: pre-wrap; }}
  .fail {{ background: #fdecea; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: 6px; text-align: left; }}
  .muted {{ color: #777; }}
  button.pv {{ margin: 0; padding: 2px 10px; font-size: 13px; }}
  #preview iframe {{ width: 100%; height: 360px; border: 1px solid #ddd; }}
</style>
</head>
<body>
<h1>구글맵 마커 추가</h1>
<form method="post" action="/add">
  <label for="urls">구글맵 링크 (한 줄에 하나)</label>
  <textarea id="urls" name="urls" required autofocus></textarea>
  <div class="row">
    <div><label for="tag">태그 (선택)</label><input id="tag" name="tag" list="tags"></div>
    <div><label for="note">메모 (선택)</label><input id="note" name="note"></div>
  </div>
  <datalist id="tags">{tag_options}</datalist>
  <button type="submit">추가</button>
</form>
{result}
<h2>저장된 장소 {count}곳 <a href="/places.csv" class="muted" style="font-size:14px">CSV 다운로드</a></h2>
<div id="preview" hidden>
  <p><b id="preview-name"></b> <span class="muted" id="preview-coords"></span>
     <span class="muted">— 핀이 해당 시설 위에 있는지 확인하세요.</span></p>
  <iframe id="preview-map" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
</div>
<table>
  <tr><th>이름</th><th>태그</th><th>메모</th><th>추가일</th><th>좌표 확인</th></tr>
  {rows}
</table>
<script>
  function preview(btn) {{
    var lat = btn.dataset.lat, lng = btn.dataset.lng;
    document.getElementById("preview-name").textContent = btn.dataset.name;
    document.getElementById("preview-coords").textContent = "(" + lat + ", " + lng + ")";
    document.getElementById("preview-map").src =
      "https://maps.google.com/maps?q=" + lat + "," + lng + "&z=18&hl=ko&output=embed";
    document.getElementById("preview").hidden = false;
  }}
  document.querySelectorAll("button.pv").forEach(function (b) {{
    b.addEventListener("click", function () {{ preview(b); }});
  }});
  if ({preview_newest}) {{
    var first = document.querySelector("button.pv");
    if (first) preview(first);
  }}
</script>
</body>
</html>
"""


def place_link(row: dict) -> str:
    """원본 공유 링크(시설 페이지로 열림)를 우선하고, 없으면 좌표로 연다."""
    link = row.get("링크", "")
    if link.startswith(("https://", "http://")):
        return link
    return f"https://www.google.com/maps/search/?api=1&query={row['위도']},{row['경도']}"


def render(result: str = "", failed: bool = False, preview_newest: bool = False) -> bytes:
    rows = marker.load_rows(CSV_PATH)
    tags = sorted({r.get("태그", "") for r in rows} - {""})
    table = "\n".join(
        f'<tr><td><a href="{escape(place_link(r))}"'
        f' target="_blank">{escape(r["이름"])}</a></td>'
        f'<td>{escape(r.get("태그", ""))}</td><td>{escape(r.get("메모", ""))}</td>'
        f'<td class="muted">{escape(r.get("추가일", ""))}</td>'
        f'<td><button type="button" class="pv" data-lat="{escape(r["위도"])}" data-lng="{escape(r["경도"])}"'
        f' data-name="{escape(r["이름"])}">지도</button></td></tr>'
        for r in reversed(rows)
    ) or '<tr><td colspan="5" class="muted">아직 없습니다.</td></tr>'
    html = PAGE.format(
        tag_options="".join(f'<option value="{escape(t)}">' for t in tags),
        result=f'<pre class="{"fail" if failed else ""}">{escape(result)}</pre>' if result else "",
        count=len(rows),
        rows=table,
        preview_newest="true" if preview_newest else "false",
    )
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str = "text/html; charset=utf-8", headers: dict | None = None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send(render())
        elif self.path == "/places.csv" and CSV_PATH.exists():
            self._send(CSV_PATH.read_bytes(), "text/csv; charset=utf-8",
                       {"Content-Disposition": 'attachment; filename="places.csv"'})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/add":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        urls = [u.strip() for u in form.get("urls", [""])[0].splitlines() if u.strip()]
        tag = form.get("tag", [""])[0].strip()
        note = form.get("note", [""])[0].strip()

        messages, all_ok = [], True
        # Playwright 동기 API는 스레드 간에 공유할 수 없으므로 요청마다 브라우저를 새로 띄운다.
        with LOCK, marker.BrowserResolver() as resolver:
            for url in urls:
                ok, message = marker.add(url, CSV_PATH, note=note, tag=tag, resolver=resolver)
                messages.append(message)
                all_ok &= ok
        added = any(m.startswith("[추가]") for m in messages)
        self._send(render("\n".join(messages), failed=not all_ok, preview_newest=added))


def main() -> None:
    global CSV_PATH
    parser = argparse.ArgumentParser(description="구글맵 마커 추가 웹 UI")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--csv", type=Path, default=CSV_PATH, help="저장할 CSV (기본: places.csv)")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 실행 안 함")
    args = parser.parse_args()
    CSV_PATH = args.csv

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"{url} 에서 실행 중입니다. 종료: Ctrl+C")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
