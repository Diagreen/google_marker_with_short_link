import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import marker

PLACE_URL = (
    "https://www.google.com/maps/place/%EA%B8%88%EA%B0%81%EC%82%AC/"
    "@35.0393791,135.7266146,17z/data=!3m1!4b1!4m6!3m5!1s0x6001a8195ec95eb1:0x1b0a4fa3f3a4a1d3"
    "!8m2!3d35.0393747!4d135.7291895!16zL20vMDFkNTRq"
)


class ParseTest(unittest.TestCase):
    def test_pin_coords_preferred_over_viewport(self):
        self.assertEqual(marker.parse_coords(PLACE_URL), (35.0393747, 135.7291895))

    def test_place_name(self):
        self.assertEqual(marker.parse_name(PLACE_URL), "금각사")

    def test_viewport_only_is_not_trusted(self):
        # 화면 중심 좌표는 장소 위치가 아닐 수 있다(IP 기준 기본 위치가 찍힌 적이 있다).
        url = "https://www.google.com/maps/@37.5665,126.978,15z"
        self.assertIsNone(marker.parse_coords(url))

    def test_query_coords(self):
        url = "https://maps.google.com/?q=-33.8568,151.2153"
        self.assertEqual(marker.parse_coords(url), (-33.8568, 151.2153))
        self.assertIsNone(marker.parse_name(url))

    def test_query_name_without_coords(self):
        url = "https://maps.google.com/maps?q=Tokyo+Tower,+Minato&ftid=0x0:0x1"
        self.assertIsNone(marker.parse_coords(url))
        self.assertEqual(marker.parse_name(url), "Tokyo Tower")


class FakeResolver:
    def __init__(self, final=None, error=None):
        self.final, self.error, self.calls = final, error, []

    def resolve(self, url, screenshot=None):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.final


LOADED_URL = (
    "https://www.google.com/maps/place/%EC%99%80%ED%83%80%EB%82%98%EB%B2%A0%EC%B9%B4%EB%A0%88/"
    "@34.6963,135.4952,17z/data=!3m1!4b1!4m6!3m5!1s0x6000e6f320eaaaab:0x7c1945593b9e0795"
    "!8m2!3d34.6963468!4d135.4977123!16s"
)


class AddTest(unittest.TestCase):
    def test_short_link_resolved_by_browser(self):
        resolver = FakeResolver(final=LOADED_URL)
        with TemporaryDirectory() as d:
            path = Path(d) / "places.csv"
            ok, _ = marker.add("https://maps.app.goo.gl/NEecvr66Yyj8yvus6", path, resolver=resolver)
            self.assertTrue(ok)
            row = marker.load_rows(path)[0]
            self.assertEqual((row["이름"], row["위도"], row["경도"]), ("와타나베카레", "34.6963468", "135.4977123"))

    def test_browser_url_skips_browser(self):
        resolver = FakeResolver(error=AssertionError("should not be called"))
        with TemporaryDirectory() as d:
            self.assertTrue(marker.add(PLACE_URL, Path(d) / "places.csv", resolver=resolver)[0])
        self.assertEqual(resolver.calls, [])

    def test_no_pin_after_loading_fails(self):
        # 로드가 끝나도 핀 좌표가 없으면 화면 중심 좌표로 추측하지 않는다.
        resolver = FakeResolver(final="https://www.google.com/maps/@35.8486769,127.1365632,15z")
        with TemporaryDirectory() as d:
            path = Path(d) / "places.csv"
            ok, message = marker.add("https://maps.app.goo.gl/x", path, resolver=resolver)
            self.assertFalse(ok)
            self.assertIn("좌표를 찾지 못했습니다", message)
            self.assertFalse(path.exists())

    def test_add_and_skip_duplicate(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "places.csv"
            self.assertTrue(marker.add(PLACE_URL, path, note="첫 방문", tag="명소/절")[0])
            ok, message = marker.add(PLACE_URL, path)
            self.assertTrue(ok)
            self.assertIn("건너뜀", message)
            rows = marker.load_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["이름"], "금각사")
            self.assertEqual(rows[0]["메모"], "첫 방문")
            self.assertEqual(rows[0]["태그"], "명소/절")
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_browser_error_is_reported(self):
        resolver = FakeResolver(error=RuntimeError("timeout"))
        with TemporaryDirectory() as d:
            ok, message = marker.add("https://maps.app.goo.gl/x", Path(d) / "places.csv", resolver=resolver)
        self.assertFalse(ok)
        self.assertIn("timeout", message)


if __name__ == "__main__":
    unittest.main()
