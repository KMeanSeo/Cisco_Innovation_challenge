# 🚀 CISCO INNOVATION CHALLENGE 2025

## Meraki MV camera detection (Custom model Case 기준)

### 프로젝트 개요

- Cisco Meraki 카메라로부터 MQTT 메시지를 수신하여 실시간으로 사람과 킥보드를 탐지한다.
- 탐지 결과를 분석하여 점자 블록과 킥보드가 겹치면 주차 위반으로 판단하고, Cisco Meraki Snapshot API로 위반 현장을 캡처하여 관리자에게 Webex 메시지를 전송한다.
- 히트맵 기반 분석을 통해 보행 방해 요소를 파악하고 이를 시각화하여 관리 효율성을 높인다.

---

## 주요 기능

- MQTT 기반 실시간 객체 탐지 및 주차 위반 감지

- 주차 위반 시, Cisco Meraki API를 활용한 즉각적인 현장 사진 캡처

- Webex Chatbot API를 통한 위반 현장 즉시 보고 (사진+텍스트)

- 히트맵 이미지 분석을 통한 보행자 보행 방해 요소 파악 및 시각화

- Meraki MV Camera MQTT 연동: /custom_analytics 토픽으로 객체 감지 데이터 수신

- Meraki Snapshot API 활용: 감지 시점 기반의 스냅샷 이미지 요청 및 다운로드

- 위경도 추정: 감지된 PM의 화면 위치를 바탕으로 지도 좌표 계산

- 감지/스냅샷 자동화: 사람이 중심 근처에 들어오면 1분 후 스냅샷 요청 자동 실행

- 저장 및 후속 처리 자동화: 이미지 및 JSON 저장 후 별도 업로드 스크립트 실행

---

## 개발 환경

- OS: Ubuntu 20.04 / macOS
- Python 3.10 이상
- OpenCV
- Ultralytics YOLO
- Pillow (PIL)
- paho-mqtt
- requests

---

## 사용한 주요 API 문서

- [Cisco Meraki MQTT Camera Analytics](https://developer.cisco.com/meraki/mv-sense/mqtt/)
- [Cisco Meraki Snapshot API](https://developer.cisco.com/meraki/api-v1/get-device-camera-snapshot/)
- [Cisco Webex Messaging API](https://developer.webex.com/docs/api/v1/messages/)

---

## 사전 준비 및 환경 설정 (Custom model Case 기준)

1. MQTT 브로커 설정 및 Meraki 카메라의 MQTT 송신 활성화
2. Meraki API 키 발급 및 카메라 시리얼 확인
3. `assets/webex_api_key.json` 파일 생성 (내용: `BOT_API_KEY`, `ROOM_ID`)
4. 객체 탐지 모델 파일(`model.tflite`)을 `models/` 폴더에 배치
5. `output/images/`, `output/json/` 폴더 자동 생성 (권한 설정 필수)
6. 분석할 테스트 영상은 `test_assets/` 폴더에 배치

---

## 프로젝트 아키텍처 (Custom model Case 기준)

```
Meraki 카메라(MQTT) → 객체 탐지 → 점자 블록 위 주차 위반 판단
        ↓
Meraki Snapshot API 호출 (현장 사진 캡처)
        ↓
Webex API (위반 현장 이미지 및 정보 전송)
        ↓
관리자 실시간 알림 수신
```

---

## 구현 방법 및 과정

### 실시간 탐지 및 분석

1. MQTT 클라이언트 설정 및 연결

```python
client = mqtt.Client()
client.username_pw_set(username="MQTT_USER", password="MQTT_PASSWORD")
client.connect("MQTT_BROKER_IP", 1883, 60)
client.subscribe("/merakimv/<카메라시리얼>/custom_analytics")
client.loop_forever()
```

2. 객체 탐지 및 중심 좌표 기반 판단

```python
if 0.4 <= center_x <= 0.6:
    # 중심 영역에 객체가 있으면 위반 의심
    # GPS 좌표 계산 로직 실행
```

3. Snapshot API 호출 및 이미지 다운로드

```python
POST https://api.meraki.com/api/v1/devices/<DEVICE_SERIAL>/camera/generateSnapshot
Headers: {
    "X-Cisco-Meraki-API-Key": "API_KEY",
    "Content-Type": "application/json"
}
Body: {
    "timestamp": "ISO_TIMESTAMP",
    "fullframe": False
}
```

4. 이미지 및 JSON 저장 후 Webex 알림 발송

- 이미지 저장 후 `detection_upload.py` 스크립트를 통해 Webex로 전송

```python
subprocess.Popen(["python3", detection_upload_path, image_path, json_path])
```

### 주차 구역 주차 여부 파악

해당 프로젝트는 Meraki 카메라로부터 수집된 객체 감지 데이터를 활용하여, 객체가 특정 구역에 **3분(180초) 이상 체류했는지 여부를 판단**합니다. 주차 위반이나 보행자 혼잡 구간 감지 등의 상황에서 활용 가능합니다.

---

## 📁 입력 데이터 포맷 (JSON)

1. JSON 형식의 객체 감지 데이터 입력

```json
{
  "label": "Braille Block",
  "ts": 1713332400000,
  "objects": [
    {
      "object_id": 1,
      "type": "person",
      "ts_entered": 1713332100000,
      "ts_exited": 1713332400000
    },
    {
      "object_id": 2,
      "type": "car",
      "ts_entered": 1713332100000,
      "ts_exited": 0
    }
  ]
}
```

- `ts_entered`: 객체가 구역에 진입한 시간 (Unix timestamp)
- `ts_exited`: 객체가 구역에 퇴장한 시간 (Unix timestamp). `0`이면 퇴장하지 않음
- `label`: 구역 이름
- `ts`: 데이터 수집 시각 (Unix timestamp)

2.  객체별 체류 시간 계산 및 상태(status) 설정

- 체류 시간`(ts_exited - ts_entered)`이 3분(180,000ms) 이상인 경우 `status = 1` (장기 체류로 간주), 그 외에는 `status = 0`
- `ts_exited`가 0이면 현재까지 퇴장하지 않은 것으로 간주하여 `status = 0`

```
duration = ts_exited - ts_entered
status = 1 if duration >= 180000 else 0
```

3. 출력 데이터

- 객체별 `object_id`, `type`, `status` 정보와 전체 `label`, `ts`를 포함한 결과 JSON 반환

```
{
  "labels": "zone_1",
  "ts": 1713332400000,
  "objects": [
    {
      "object_id": 1,
      "type": "person",
      "status": 1
    }
  ]
}
```

4. 주요 함수 설명

```
def process_occupancy_data(input_data):
    # 입력 데이터 파싱
    # 객체별 체류 시간 계산
    # 3분 이상이면 status=1 설정
    # 최종 결과 JSON 반환
```

### 히트맵 기반 보행 방해 요소 파악 [Meraki Default model Case 기준]

1. 히트맵 이미지 색상 범위 지정(HSV 색 공간 활용)

```python
# 빨강, 주황, 노랑 HSV 범위 설정
red_range = [(0,120,100), (10,255,255)], [(170,120,100), (180,255,255)]
orange_range = [(11,120,100), (25,255,255)]
yellow_range = [(26,120,100), (35,255,255)]
```

2. 각 색상별 마스크 생성 및 전처리

```python
mask = cv2.inRange(hsv_image, lower_color, upper_color)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
```

3. 폴리곤(다각형) 추출 및 포함 관계 분석

```python
polygons = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
```

4. 주황 및 빨강 영역이 노랑 영역에 포함되지 않은 경우 별도 표기 (위반 영역)

```python
def is_contour_inside(inner, outer):
    for point in inner:
        if cv2.pointPolygonTest(outer, tuple(point[0]), False) < 0:
            return False
    return True
```

5. 결과 시각화

- 보행 방해 요소를 파악하고 이를 시각화하여 관리자가 주차 문제 지역을 직관적으로 파악 가능하도록 제공

---

## 결과 확인 및 분석

- 실시간 알림은 Cisco Webex로 전송된다.
- 히트맵 분석 이미지는 로컬에서 확인하며, 주기적으로 분석된 이미지를 통해 장기적인 관리 대책 마련 가능

---

## 참고사항

- MQTT, Cisco API 키 등 민감정보는 별도의 설정 파일로 관리
- 프로그램 실행은 가상환경 내에서 진행 권장
- 해당 설명은 Custom model을 Meraki 카메라에 올리는 케이스 기반 설명 (Custom model 사용시, Meraki Analytics 기능 사용 불가)
- Meraki: Default Model + 서버: Custom model 조합으로 아키텍처 구성 가능
