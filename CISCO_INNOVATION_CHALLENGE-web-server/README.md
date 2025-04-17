# 🚀 CISCO INNOVATION CHALLENGE 2025

## Web Server

## 주요 기능

1. 객체 탐지 이벤트 수신 및 저장
2. 반납 요청 및 리워드 처리

- 사용자가 반납한 PM을 사진으로 촬영한 후 Cisco Webex Embedded App을 통해 이미지 업로드 및 반납 요청
- 서버에서 업로드된 이미지로 PM 인증 여부를 판단한 후, 사용자와 가장 가까운 MV camera에게 실시간 확인 요청
- MV camera 가 주차 위반 여부 판단 및 결과 전송
- 주변에 주차 위반된 다른 PM이 있으면, 사용자에게 정리 요청
- 사용자가 정리를 완료하였다면, 재확인 후 리워드 제공

3. 최근 이벤트 모니터링 웹 페이지 제공

---

# Django Web Server Setup Guide

## 개발 환경

- 운영체제: Ubuntu 20.04 / macOS
- Python 3.10 이상
- Django 4.x
- SQLite 사용
- 가상환경 사용 권장 (venv 또는 virtualenv)

## 사용한 기술 스택 및 주요 라이브러리

- Django: 웹 프레임워크
- SQLite: 경량 데이터베이스
- Pillow: 이미지 처리 라이브러리
- Ultralytics YOLO: 객체 탐지 모델
- paho-mqtt: MQTT 통신 처리용

### requirements.txt 내용

```
django>=4.0
pillow
ultralytics
paho-mqtt
```

## Django 서버 실행 방법

1. 프로젝트 루트에서 가상환경 생성 및 활성화

```bash
python3 -m venv venv
source venv/bin/activate
```

2. 패키지 설치

```bash
pip install -r requirements.txt
```

3. 마이그레이션 실행

```bash
python3 ./CISCO_INNOVATION_CHALLENGE/CISCO_INNOVATION_CHALLENGE/cisco_server/manage.py migrate
```

4. 서버 실행

```bash
python3 ./CISCO_INNOVATION_CHALLENGE/CISCO_INNOVATION_CHALLENGE/cisco_server/manage.py runserver 0.0.0.0:8000
```

---

## 사전 준비 및 세팅 내용

- Python 3.10 이상이 설치되어 있어야 함
- `CISCO_INNOVATION_CHALLENGE` 디렉토리 내부에 `cisco_server` 디렉토리와 `manage.py`가 존재해야 함
- SQLite 사용으로 별도의 데이터베이스 설정은 필요 없음
- MQTT 브로커는 로컬에서 실행된다고 가정(`localhost:1883`).

---

## API 명세

| 경로               | 설명                  |
| ------------------ | --------------------- |
| `/register/`       | 사용자 등록           |
| `/request-reward/` | 리워드 요청           |
| `/readjust/`       | 재조정 이미지 업로드  |
| `/monitor/`        | 감지 로그 웹 모니터링 |

자세한 MQTT 포맷은 Cisco 공식 문서를 참조한다:  
🔗 [Meraki MV Sense MQTT API Docs](https://developer.cisco.com/meraki/mv-sense/mqtt/#raw-detections-a-list-containing-object-identifiers-oids-and-their-x-y-coordinates)

---

## 프로젝트 아키텍처

### 구성

- YOLO → 객체 탐지
- 탐지 결과 → MQTT Publish (`custom_cv/<serial>`)
- Django Subscriber → MQTT 메시지를 받아 Event 저장
- 사용자 → API 호출로 보상 요청
- 서버 → 탐지 여부 확인 후 보상 판단

### 데이터 흐름

```
YOLO 모델 → MQTT 메시지 전송 → Django 서버 수신
                                  ↓
                            DB에 이벤트 저장
                                  ↓
         사용자 보상 요청 API 호출 (request-reward)
                                  ↓
             이벤트 내용 확인 후 success/failed 판단
```

---

## 구현 방법 및 과정

### 1. Django 프로젝트 생성 및 앱 구성

```bash
django-admin startproject cisco_server
cd cisco_server
python manage.py startapp cisco_be_launch
```

### 2. 모델 정의

- `Camera`: 시리얼 번호와 위도/경도를 저장
- `Event`: MQTT 메시지를 받아 저장하는 이벤트 테이블
- `User`: 이메일 기반 유저 정보와 리워드 점수를 관리

```python
class Camera(models.Model):
    serial = models.CharField(max_length=50, unique=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

class Event(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

class User(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    reward = models.IntegerField(default=0)
```

### 3. MQTT 메시지 처리

- paho-mqtt를 사용하여 `custom_cv/#` 토픽을 구독
- 메시지를 수신하면 payload의 timestamp, outputs의 location 데이터를 추출
- 대응되는 Camera가 없으면 생성하고 Event에 저장
