import paho.mqtt.client as mqtt
import json
import os
import time
import math
import requests
import threading
import subprocess
from datetime import datetime, timezone

# 설정
API_KEY = "API_KEY"
DEVICE_SERIAL = "DEVICE_SERIAL"
MQTT_BROKER = "BROKER_IP"
MQTT_TOPIC = "/merakimv/<DEVICE_SERIAL>/custom_analytics"
MQTT_USER = "MQTT_USER"
MQTT_PASSWORD = "MQTT_PASSWORD"

CAMERA_LAT = 37.7749
CAMERA_LNG = -122.4194
CAMERA_HEADING = 90
CAMERA_FOV = 60
FIXED_DISTANCE = 10.0

base_dir = os.path.dirname(os.path.abspath(__file__))
output_folder = os.path.join(base_dir, "../../output/")
json_folder = os.path.join(output_folder, "json")
image_folder = os.path.join(output_folder, "images")
os.makedirs(json_folder, exist_ok=True)
os.makedirs(image_folder, exist_ok=True)

last_detection_time = 0  # 최근 감지 시간 저장용 (중복 방지)

# snapshot 다운로드 함수
def download_snapshot(image_url, image_path, json_path, save_data, max_attempts=5, delay=2):
    for attempt in range(max_attempts):
        print(f"[{attempt+1}/{max_attempts}] 스냅샷 다운로드 시도 중...")
        res = requests.get(image_url)

        if (res.status_code == 200 or res.status_code == 202) and 'image' in res.headers.get("Content-Type", ""):
            with open(image_path, 'wb') as f:
                f.write(res.content)
            with open(json_path, 'w') as f:
                json.dump(save_data, f, indent=2)

            print(f"[✅ 저장 완료] 이미지: {image_path}")
            print(f"[✅ 저장 완료] JSON: {json_path}")

            detection_upload_path = os.path.join(base_dir, "../cisco_apis/detection_upload.py")
            subprocess.Popen(["python3", detection_upload_path, image_path, json_path])
            return
        else:
            print(f"❗ 다운로드 실패(status: {res.status_code}) → {delay}초 후 재시도")
            time.sleep(delay)

    print("❌ 스냅샷 다운로드 재시도 초과. 이미지 저장 실패.")

# snapshot 요청 함수
def request_snapshot(timestamp, save_data):
    ISOTimestamp = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    headers = {
        "X-Cisco-Meraki-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "timestamp": ISOTimestamp,
        "fullframe": False
    }

    snapshot_url = f"https://api.meraki.com/api/v1/devices/{DEVICE_SERIAL}/camera/generateSnapshot"
    print(f">>>>>>>>>>>>>>> {ISOTimestamp}")
    res = requests.post(snapshot_url, headers=headers, json=body)

    if res.status_code == 200 or res.status_code == 202:
        try:
            snapshot_data = res.json()
            image_url = snapshot_data.get("url")
            if not image_url:
                print("[에러] Snapshot URL 없음")
                return

            image_path = os.path.join(image_folder, f"snapshot_{timestamp}.jpg")
            json_path = os.path.join(json_folder, f"snapshot_{timestamp}.json")
            print("10초 뒤에 이미지 url 요청")
            threading.Timer(10, download_snapshot, args=(image_url, image_path, json_path, save_data)).start()

        except Exception as e:
            print(f"[에러] 응답 파싱 실패: {e}")
    else:
        print(f"[에러] 스냅샷 요청 실패: {res.status_code} - {res.text}")

def request_snapshot(timestamp, save_data, max_attempts=5, delay=3):
    ISOTimestamp = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    headers = {
        "X-Cisco-Meraki-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "timestamp": ISOTimestamp,
        "fullframe": False
    }

    snapshot_url = f"https://api.meraki.com/api/v1/devices/{DEVICE_SERIAL}/camera/generateSnapshot"

    for attempt in range(max_attempts):
        print(f"[{attempt+1}/{max_attempts}] 스냅샷 요청 시도 중... 시간: {ISOTimestamp}")
        res = requests.post(snapshot_url, headers=headers, json=body)

        if res.status_code == 200 or res.status_code == 202:
            try:
                snapshot_data = res.json()
                image_url = snapshot_data.get("url")
                if not image_url:
                    print("[에러] Snapshot 응답에 URL 없음 → 재시도")
                    time.sleep(delay)
                    continue

                image_path = os.path.join(image_folder, f"snapshot_{timestamp}.jpg")
                json_path = os.path.join(json_folder, f"snapshot_{timestamp}.json")
                threading.Thread(
                    target=download_snapshot,
                    args=(image_url, image_path, json_path, save_data),
                    kwargs={"max_attempts": 5, "delay": 2}
                ).start()
                return  # 성공했으면 종료

            except Exception as e:
                print(f"[에러] 응답 파싱 실패: {e} → 재시도")
        else:
            print(f"[에러] 요청 실패: {res.status_code} - {res.text} → 재시도")

        time.sleep(delay)  # 다음 시도까지 대기

    print("❌ 스냅샷 요청 재시도 초과. 요청 실패.")

# MQTT 메시지 수신 시 처리
def on_message(client, userdata, msg):
    global last_detection_time
    payload = json.loads(msg.payload.decode('utf-8'))
    print(payload)
    try:

        outputs = payload.get("outputs", [])
        timestamp = payload.get("timestamp")
        save_data = []

        now = time.time()
        if now - last_detection_time < 30:
            return

        for obj in outputs:
            if obj.get("class") == 0:
                box = obj.get("location")  # [x1, y1, x2, y2] normalized
                if not box:
                    continue
                x1, y1, x2, y2 = box
                center_x = (x1 + x2) / 2

                if 0.4 <= center_x <= 0.6:  # 중심 근처 감지 기준
                    # 위경도 추정
                    relative_offset = center_x - 0.5
                    angle_offset = relative_offset * CAMERA_FOV
                    absolute_angle = CAMERA_HEADING + angle_offset
                    dx = FIXED_DISTANCE * math.sin(math.radians(absolute_angle))
                    dy = FIXED_DISTANCE * math.cos(math.radians(absolute_angle))
                    delta_lat = dy / 111320
                    delta_lng = dx / (111320 * math.cos(math.radians(CAMERA_LAT)))
                    lat = CAMERA_LAT + delta_lat
                    lng = CAMERA_LNG + delta_lng

                    save_data.append({
                        "object_id": obj.get("object_id"),
                        "lat": lat,
                        "lng": lng,
                        "timestamp": datetime.fromtimestamp(timestamp / 1000).isoformat()
                    })

                    last_detection_time = now

                    # 60초 후 스냅샷 예약
                    print("✅ 중심 근처에서 사람 감지됨 → 60초 후 스냅샷 예약")
                    threading.Timer(60, request_snapshot, args=(timestamp, save_data)).start()
                    break
        else:
            print("🙅 중심 근처에 사람 감지되지 않음")

    except Exception as e:
        print(f"[에러] 메시지 처리 중 문제 발생: {e}")



# MQTT 연결 시 호출
def on_connect(client, userdata, flags, rc):
    print("[MQTT] 연결 성공, 토픽 구독 시작")
    client.subscribe(MQTT_TOPIC)

# MQTT 클라이언트 설정
client = mqtt.Client()
client.username_pw_set(username="admin", password="sb13579!")
client.on_connect = on_connect
client.on_message = on_message

print(f"[MQTT] 브로커 연결 중… ({MQTT_BROKER})")
client.connect(MQTT_BROKER, 1883, 60)
client.loop_forever()
