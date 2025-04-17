#!/usr/bin/env python3
import os
import sys
import django
import json
import time
import threading
import math
import cv2
import subprocess
import queue
from glob import glob
from datetime import datetime
import tkinter as tk
from PIL import Image, ImageTk
from ultralytics import YOLO
import paho.mqtt.client as mqtt  # MQTT 전송을 위한 import

# ------------------------------------------------------------------
# Django 환경 설정 (Camera 모델 사용을 위함)
# ------------------------------------------------------------------
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'cisco_be'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cisco_be.settings")
django.setup()
from cisco_be_launch.models import Camera  # Django 모델

# ------------------------------------------------------------------
# MQTT 클라이언트 설정 (발행)
# ------------------------------------------------------------------
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()  # 백그라운드 스레드에서 이벤트 처리

# ------------------------------------------------------------------
# 기본 경로, 모델 로드, 출력 폴더 설정
# ------------------------------------------------------------------
base_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(base_dir, "../../models/model.pt")
model = YOLO(model_path)

print("[MODEL INFORMATION]")
print("-" * 30)
print(f"Number of classes: {len(model.names)}")
print("Class names:")
for class_id, name in model.names.items():
    print(f"    [{class_id}] {name}")

output_folder = os.path.join(base_dir, "../../output/")
json_folder = os.path.join(output_folder, "json")
image_folder = os.path.join(output_folder, "images")
os.makedirs(json_folder, exist_ok=True)
os.makedirs(image_folder, exist_ok=True)

# ------------------------------------------------------------------
# Tkinter 및 디스플레이 큐 (메인 스레드 GUI 업데이트)
# ------------------------------------------------------------------
gui_queue = queue.Queue()
display_queue = queue.Queue()
quit_flag = False  # 전역 종료 플래그

# ------------------------------------------------------------------
# 상수 (원래 하드코딩된 카메라 값, 필요시 기본값으로 사용)
# 이제 실제 Camera("test") 객체의 좌표를 우선 사용할 예정
DEFAULT_CAMERA_LAT = 37.7749
DEFAULT_CAMERA_LNG = -122.4194
CAMERA_HEADING = 90
CAMERA_FOV = 60
FIXED_DISTANCE = 10.0

# ------------------------------------------------------------------
# Tkinter 큐 처리 함수
# ------------------------------------------------------------------
def process_queue(root):
    try:
        while True:
            image, window_title, duration = gui_queue.get_nowait()
            win = tk.Toplevel(root)
            win.title(window_title)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
            tk_image = ImageTk.PhotoImage(pil_image)
            label = tk.Label(win, image=tk_image)
            label.image = tk_image
            label.pack()
            win.after(duration, win.destroy)
    except queue.Empty:
        pass
    root.after(100, process_queue, root)

def process_display_queue():
    global quit_flag
    try:
        while not display_queue.empty():
            frame = display_queue.get_nowait()
            cv2.imshow("Detection", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                quit_flag = True
    except queue.Empty:
        pass
    root.after(30, process_display_queue)

def show_image_with_tkinter(image, window_title, duration=3000):
    gui_queue.put((image, window_title, duration))

# ------------------------------------------------------------------
# MQTT 전송 함수: detection 데이터를 JSON으로 발행
# ------------------------------------------------------------------
def send_mqtt_detection(lat, lng):
    detection_payload = {
        # 현재 시각의 에포크 밀리초 값
        "timestamp": int(datetime.now().timestamp() * 1000),
        "outputs": [{
            "location": [lat, lng]
        }]
    }
    topic = "custom_cv/test"  # Camera의 serial이 test임을 가정
    mqtt_client.publish(topic, json.dumps(detection_payload))
    print(f"MQTT 메시지 발행: topic={topic}, payload={detection_payload}")

# ------------------------------------------------------------------
# 겹침(Overlap) 검사 및 저장, MQTT 전송 함수 (수정됨)
# ------------------------------------------------------------------
def save_if_overlap(results, frame):
    im = frame.copy()
    kb_boxes = []
    block_boxes = []
    detections = []  # MQTT로 보낼 detection 데이터

    # 분류: kb (예: 클래스 인덱스 1)와 block (예: 클래스 인덱스 0)
    for r in results:
        for box in r.boxes:
            cls = int(box.cls.item())
            cls_name = model.names[cls]
            conf = float(box.conf.item())
            x1, y1, x2, y2 = [int(x.item()) for x in box.xyxy[0]]
            if cls == 1:
                kb_boxes.append((cls, cls_name, conf, (x1, y1, x2, y2)))
            elif cls == 0:
                block_boxes.append((x1, y1, x2, y2))

    height, width, _ = im.shape

    # 실질적 좌표 계산 전에, 데이터베이스에서 serial="test"인 Camera 조회
    try:
        cam_obj = Camera.objects.get(serial="test")
        base_lat = cam_obj.lat if cam_obj.lat is not None else DEFAULT_CAMERA_LAT
        base_lng = cam_obj.lng if cam_obj.lng is not None else DEFAULT_CAMERA_LNG
    except Camera.DoesNotExist:
        base_lat = DEFAULT_CAMERA_LAT
        base_lng = DEFAULT_CAMERA_LNG

    # 키보드와 블록이 겹치는지 검사하고, 겹치면 경도 좌표 계산
    for kb_cls, kb_cls_name, kb_conf, kb_box in kb_boxes:
        for block_box in block_boxes:
            if boxes_overlap(kb_box, block_box):
                x1, y1, x2, y2 = kb_box
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                relative_offset = (center_x - width / 2) / (width / 2)
                angle_offset = relative_offset * (CAMERA_FOV / 2)
                absolute_angle = CAMERA_HEADING + angle_offset
                dx = FIXED_DISTANCE * math.sin(math.radians(absolute_angle))
                dy = FIXED_DISTANCE * math.cos(math.radians(absolute_angle))
                delta_lat = dy / 111320
                delta_lng = dx / (111320 * math.cos(math.radians(base_lat)))
                detected_lat = base_lat + delta_lat
                detected_lng = base_lng + delta_lng
                # detection 데이터 구성 (여기 object_id는 예시값)
                detection = {
                    "object_id": 1008,
                    "lat": detected_lat,
                    "lng": detected_lng,
                    "timestamp": datetime.now().isoformat()
                }
                detections.append(detection)
                # 한 번 겹치면 break; (한 객체 당 한 번 처리)
                break

    # 모든 박스에 대해 테두리 및 레이블 표시 (화면용)
    for r in results:
        for box in r.boxes:
            cls = int(box.cls.item())
            cls_name = model.names[cls]
            conf = float(box.conf.item())
            x1, y1, x2, y2 = [int(x.item()) for x in box.xyxy[0]]
            color = (0, 255, 0) if cls == 1 else (255, 0, 0) if cls == 0 else (0, 255, 255)
            cv2.rectangle(im, (x1, y1), (x2, y2), color, 2)
            cv2.putText(im, f"{cls_name}:{conf:.2f}", (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # 만약 detection이 발생하면, 파일 저장과 함께 MQTT 전송 진행
    if detections:
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        image_path = os.path.join(image_folder, f"frame_{timestamp_str}.jpg")
        json_path = os.path.join(json_folder, f"detection_{timestamp_str}.json")
        cv2.imwrite(image_path, im)
        with open(json_path, 'w') as f:
            json.dump(detections, f, indent=2)
        print(f"[{timestamp_str}] KB-BLOCK overlap detected. Saved image and JSON.")
        print("Saved JSON data:")
        print(json.dumps(detections, indent=2))
        show_image_with_tkinter(im, f"Saved Detection {timestamp_str}", 3000)
        # MQTT 메시지 발행: 여러 detection이 있다면 여기서는 첫 번째 것으로 발행하거나 모두 포함
        # 예를 들어, 발행 메시지의 outputs 배열에 모든 detection의 [lat, lng]를 추가
        outputs = [{"location": [det["lat"], det["lng"]]} for det in detections]
        mqtt_payload = {
            "timestamp": int(datetime.now().timestamp() * 1000),
            "outputs": outputs
        }
        topic = "custom_cv/test"
        mqtt_client.publish(topic, json.dumps(mqtt_payload))
        print(f"Published MQTT message to topic {topic}: {mqtt_payload}")
        # 기존에 external 스크립트를 호출하는 부분이 있다면 필요에 따라 유지 또는 삭제:
        detection_upload_path = os.path.join(base_dir, "../cisco_apis/detection_upload.py")
        cmd = ["python3", detection_upload_path, image_path, json_path]
        subprocess.Popen(cmd)

# ------------------------------------------------------------------
# 겹침(Overlap) 판별 도우미 함수
# ------------------------------------------------------------------
def boxes_overlap(box1, box2):
    x1_max = max(box1[0], box2[0])
    y1_max = max(box1[1], box2[1])
    x2_min = min(box1[2], box2[2])
    y2_min = min(box1[3], box2[3])
    return x1_max < x2_min and y1_max < y2_min

# ------------------------------------------------------------------
# 비디오에서 객체 감지 수행 함수
# ------------------------------------------------------------------
def detect_objects_in_video(video_path):
    global quit_flag
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return
    last_overlap_check_time = time.time()
    target_fps = 30
    last_results = []
    while not quit_flag:
        ret, frame = cap.read()
        if not ret:
            break
        last_results = model(frame, verbose=False)
        current_time = time.time()
        if current_time - last_overlap_check_time >= 1.0:
            threading.Thread(target=save_if_overlap, args=(last_results, frame.copy())).start()
            last_overlap_check_time = current_time

        # 프레임에 감지 결과 표시
        im = frame.copy()
        for r in last_results:
            for box in r.boxes:
                cls = int(box.cls.item())
                cls_name = model.names[cls]
                conf = float(box.conf.item())
                x1, y1, x2, y2 = [int(x.item()) for x in box.xyxy[0]]
                color = (0, 255, 0) if cls == 1 else (255, 0, 0) if cls == 0 else (0, 255, 255)
                cv2.rectangle(im, (x1, y1), (x2, y2), color, 2)
                cv2.putText(im, f"{cls_name}:{conf:.2f}", (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        if not display_queue.full():
            display_queue.put(im)
    cap.release()
    cv2.destroyAllWindows()

# ------------------------------------------------------------------
# 테스트 에셋 내의 모든 비디오에 대해 객체 감지 수행
# ------------------------------------------------------------------
def start_detection():
    test_assets_path = os.path.join(base_dir, "../test_assets/*.mp4")
    video_files = sorted(glob(test_assets_path))
    if not video_files:
        print("No .mp4 files found in test_assets/")
    else:
        for video_path in video_files:
            print(f"\nprocessing: {os.path.basename(video_path)}")
            detect_objects_in_video(video_path)
            if quit_flag:
                break

# ------------------------------------------------------------------
# 메인: Tkinter 및 객체 감지 시작
# ------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 메인 창 숨기기
    root.after(100, process_queue, root)
    root.after(30, process_display_queue)

    detection_thread = threading.Thread(target=start_detection, daemon=True)
    detection_thread.start()

    root.mainloop()