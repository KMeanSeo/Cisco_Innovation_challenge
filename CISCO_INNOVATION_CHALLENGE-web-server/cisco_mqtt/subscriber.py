import os
import sys
import django
import json
from datetime import datetime
import paho.mqtt.client as mqtt
from cisco_be_launch.models import Camera, Event

# 프로젝트 루트 경로에 맞게 sys.path에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'cisco_server'))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cisco_be.settings")
django.setup()



def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    # 구독 토픽: custom_cv 이후에 카메라 고유번호가 올 것으로 가정
    client.subscribe("custom_cv/#") 

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        
        # timestamp (밀리초 단위) -> datetime 객체로 변환
        timestamp_ms = data.get("timestamp", 0)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
        
        # outputs 배열에서 위치 정보 추출
        outputs = data.get("outputs", [])
        lat = None
        lng = None
        if outputs:
            output0 = outputs[0]
            location = output0.get("location")
            if location and isinstance(location, list) and len(location) >= 2:
                lat = float(location[0])
                lng = float(location[1])
        
        # MQTT 토픽에서 카메라 시리얼 번호 추출
        topic_parts = msg.topic.split("/")
        camera_serial_number = topic_parts[-1] if len(topic_parts) > 1 else "unknown"
        
        # Camera 객체 가져오거나 생성
        camera, created = Camera.objects.get_or_create(serial=camera_serial_number)
        
        # Event 객체 생성 (자동 저장)
        event = Event.objects.create(
            camera=camera,
            timestamp=timestamp,
            event_type="real_detection",
            payload=data,
            lat=lat,
            lng=lng
        )
        
        print(f"Saved Event for camera {camera_serial_number} at {timestamp}")
    except Exception as e:
        print("Error processing message:", e)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
client.connect(MQTT_BROKER, MQTT_PORT, 60)

client.loop_forever()