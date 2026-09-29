# google_marker_with_short_link

구글맵 공유 링크를 넣으면 장소 이름과 좌표를 뽑아 `places.csv`에 쌓는 도구입니다.
이 CSV를 [Google 내 지도(My Maps)](https://www.google.com/maps/d/)로 가져오면
휴대폰 구글맵 앱의 **[저장됨] → [지도]** 에서 마커를 볼 수 있습니다.

## 설치

Python 3.10 이상이 필요합니다.

```bash
pip install -r requirements.txt
playwright install chromium
```

휴대폰에서 공유한 링크(`maps.app.goo.gl`)는 풀어도 좌표가 없습니다. 좌표는 페이지의 자바스크립트가
장소를 불러온 뒤에야 주소창 URL에 붙기 때문에, 화면 없는 크롬(Playwright)으로 링크를 열고
주소창 URL을 읽습니다. 링크 하나에 몇 초 걸립니다.
PC 브라우저 주소창에서 복사한 URL(`!3d…!4d…` 포함)은 브라우저 없이 바로 처리합니다.

> 구글맵 화면을 자동으로 여는 방식이라 구글이 화면·URL 구조를 바꾸면 깨질 수 있고,
> 구글맵 약관은 자동 수집을 원칙적으로 금지합니다. 개인 기록 용도로만 쓰세요.

## 웹 UI

```bash
python webui.py
```

브라우저가 `http://127.0.0.1:8000/` 로 열립니다. 링크를 한 줄에 하나씩 붙여 넣고 **추가**를 누르면 됩니다.
태그·메모는 입력한 링크 전체에 같이 적용되고, 태그 칸은 기존에 쓴 태그를 자동완성으로 보여 줍니다.
표의 이름을 누르면 원본 링크(시설 페이지)가 열리고, **[지도]** 를 누르면 저장된 좌표에 핀을 찍은 지도가 표 위에 뜹니다.
핀이 그 시설 위에 있는지 여기서 확인하세요. 새로 추가하면 방금 추가한 장소가 자동으로 표시됩니다.
옵션: `--port 8080`, `--csv kyoto.csv`, `--no-browser`

## CLI

```bash
python marker.py https://maps.app.goo.gl/XXXX
python marker.py https://maps.app.goo.gl/AAAA https://maps.app.goo.gl/BBBB
python marker.py https://maps.app.goo.gl/XXXX --name "금각사" --tag "명소/절" --note "오전에 가면 한산"
python marker.py https://maps.app.goo.gl/XXXX --csv kyoto.csv
```

- 좌표가 같은 장소는 중복으로 보고 건너뜁니다.
- `태그`는 `--tag`로 넣거나, 나중에 CSV에서 직접 채우세요.
- 좌표를 못 찾으면 PC 브라우저에서 링크를 열고, 지도가 로드된 뒤 주소창 URL을 복사해 다시 넣으세요.
- 문제 확인용: `--debug`(최종 URL 출력, 화면을 `debug.png`로 저장), `--show-browser`(브라우저 창을 띄워서 실행)

CSV 열: `이름, 위도, 경도, 태그, 메모, 링크, 추가일`

## My Maps로 가져오기

1. My Maps에서 새 지도 → 레이어의 **가져오기** → `places.csv` 업로드
2. 위치 열: `위도`, `경도` 선택 / 마커 제목 열: `이름` 선택
3. 레이어의 **스타일 → 데이터 열로 그룹화: 태그** 를 선택하면 태그별로 색·아이콘을 다르게 지정할 수 있습니다.
4. 이후 장소를 추가했으면 레이어 메뉴의 **다시 가져오기 및 병합**으로 갱신합니다. (자동 동기화는 되지 않습니다.)

## 주의

- 엑셀에서 태그를 편집하고 저장할 때 **CSV UTF-8** 형식으로 저장하세요. 일반 CSV로 저장하면 인코딩이 바뀌어 한글이 깨질 수 있습니다.
- 좌표는 장소 핀 좌표(`!3d…!4d…`)나 `?q=위도,경도`만 씁니다. `@위도,경도`는 화면 중심이라 장소가 아닐 수 있어 쓰지 않습니다.

## 테스트

```bash
python -m unittest
```
