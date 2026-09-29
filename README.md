# google_marker_with_short_link

구글맵 공유 링크를 넣으면 장소 이름과 좌표를 뽑아 `places.csv`에 쌓는 도구입니다.
이 CSV를 [Google 내 지도(My Maps)](https://www.google.com/maps/d/)로 가져오면
휴대폰 구글맵 앱의 **[저장됨] → [지도]** 에서 마커를 볼 수 있습니다.

Python 3.10 이상, 표준 라이브러리만 사용합니다.

## 웹 UI

```bash
python webui.py
```

브라우저가 `http://127.0.0.1:8000/` 로 열립니다. 링크를 한 줄에 하나씩 붙여 넣고 **추가**를 누르면 됩니다.
태그·메모는 입력한 링크 전체에 같이 적용되고, 태그 칸은 기존에 쓴 태그를 자동완성으로 보여 줍니다.
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

CSV 열: `이름, 위도, 경도, 태그, 메모, 링크, 추가일`

## My Maps로 가져오기

1. My Maps에서 새 지도 → 레이어의 **가져오기** → `places.csv` 업로드
2. 위치 열: `위도`, `경도` 선택 / 마커 제목 열: `이름` 선택
3. 레이어의 **스타일 → 데이터 열로 그룹화: 태그** 를 선택하면 태그별로 색·아이콘을 다르게 지정할 수 있습니다.
4. 이후 장소를 추가했으면 레이어 메뉴의 **다시 가져오기 및 병합**으로 갱신합니다. (자동 동기화는 되지 않습니다.)

## 주의

- 엑셀에서 태그를 편집하고 저장할 때 **CSV UTF-8** 형식으로 저장하세요. 일반 CSV로 저장하면 인코딩이 바뀌어 한글이 깨질 수 있습니다.
- 링크 해석은 구글맵 URL 형식(`!3d…!4d…`, `@위도,경도`, `?q=위도,경도`)에 의존합니다. 구글이 형식을 바꾸면 깨질 수 있습니다.

## 테스트

```bash
python -m unittest
```
