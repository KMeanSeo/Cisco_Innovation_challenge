#!/usr/bin/env python3
import cv2
import torch
import json
import os
import time
import threading
from glob import glob
from ultralytics import YOLO
from datetime import datetime
import tkinter as tk
from PIL import Image, ImageTk
import subprocess
import queue
import math

# 기본 경로 및 모델 로드
base_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(base_dir, "../../models/model.pt")
model = YOLO(model_path)

print("[MODEL INFORMATION]")
print("-" * 30)
print(f"Number of classes: {len(model.names)}")
print("Class names:")
for class_id, name in model.names.items():
    print(f"    [{class_id}] {name}")

# 출력 폴더 설정 및 생성
output_folder = os.path.join(base_dir, "../../output/")
json_folder = os.path.join(output_folder, "json")
image_folder = os.path.join(output_folder, "images")
os.makedirs(json_folder, exist_ok=True)
os.makedirs(image_folder, exist_ok=True)

# Tkinter 및 디스플레이 큐 (메인 스레드에서의 GUI 업데이트를 위해)
gui_queue = queue.Queue()
display_queue = queue.Queue()

# 전역 종료 플래그 (사용자가 'q'를 누르면 True로 세팅)
quit_flag = False

# 카메라 및 측정 관련 상수
CAMERA_LAT = 37.7749
CAMERA_LNG = -122.4194
CAMERA_HEADING = 90
CAMERA_FOV = 60
FIXED_DISTANCE = 10.0


def process_queue(root):
    """Tkinter 큐를 처리하여 큐에 담긴 이미지 데이터를 팝업 창으로 표시"""
    try:
        while True:
            image, window_title, duration = gui_queue.get_nowait()
            win = tk.Toplevel(root)
            win.title(window_title)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
            tk_image = ImageTk.PhotoImage(pil_image)
            label = tk.Label(win, image=tk_image)
            label.image = tk_image  # 이미지 참조 유지
            label.pack()
            win.after(duration, win.destroy)
    except queue.Empty:
        pass
    root.after(100, process_queue, root)


def process_display_queue():
    """display_queue에 담긴 프레임을 가져와 cv2.imshow()로 메인 스레드에서 표시"""
    global quit_flag
    try:
        while not display_queue.empty():
            frame = display_queue.get_nowait()
            cv2.imshow("Detection", frame)
            # 1ms 기다리며 키 입력 확인 (메인 스레드에서 실행)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                quit_flag = True
    except queue.Empty:
        pass
    root.after(30, process_display_queue)


def show_image_with_tkinter(image, window_title, duration=3000):
    """이미지와 창 제목, 지속 시간을 큐에 추가하여 Tk 창에 표시"""
    gui_queue.put((image, window_title, duration))


def boxes_overlap(box1, box2):
    x1_max = max(box1[0], box2[0])
    y1_max = max(box1[1], box2[1])
    x2_min = min(box1[2], box2[2])
    y2_min = min(box1[3], box2[3])
    return x1_max < x2_min and y1_max < y2_min


def save_if_overlap(results, frame):
    im = frame.copy()
    kb_boxes = []
    block_boxes = []
    save_data = []

    # 객체 감지 결과에서 키보드(kb)와 블록(box) 정보 분류
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

    # 키보드와 블록이 겹치는지 체크하고, 겹치면 좌표 계산 후 detection 데이터 생성
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
                delta_lng = dx / (111320 * math.cos(math.radians(CAMERA_LAT)))
                lat = CAMERA_LAT + delta_lat
                lng = CAMERA_LNG + delta_lng
                detection = {
                    "object_id": 1008,
                    "lat": lat,
                    "lng": lng,
                    "timestamp": datetime.now().isoformat()
                }
                save_data.append(detection)
                break

    # 모든 박스에 대해 테두리 및 레이블 표시
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

    # 겹침이 감지되면 이미지와 JSON 저장 및 Tk 창 표시
    if save_data:
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        image_path = os.path.join(image_folder, f"frame_{timestamp_str}.jpg")
        json_path = os.path.join(json_folder, f"detection_{timestamp_str}.json")
        cv2.imwrite(image_path, im)
        with open(json_path, 'w') as f:
            json.dump(save_data, f, indent=2)
        print(f"[{timestamp_str}] KB-BLOCK overlap detected. Saved image and JSON.")
        print("Saved JSON data:")
        print(json.dumps(save_data, indent=2))
        show_image_with_tkinter(im, f"Saved Detection {timestamp_str}", 3000)
        detection_upload_path = os.path.join(base_dir, "../cisco_apis/detection_upload.py")
        cmd = ["python3", detection_upload_path, image_path, json_path]
        subprocess.Popen(cmd)


def detect_objects_in_video(video_path):
    global quit_flag
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return
    last_overlap_check_time = time.time()
    target_fps = 30
    frame_delay = int(1000 / target_fps)
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

        # 프레임에 감지 결과 표시 (박스, 레이블 등 그리기)
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
        # background 스레드에서는 화면 출력 대신 디스플레이 큐에 프레임 전달
        if not display_queue.full():
            display_queue.put(im)
    cap.release()
    cv2.destroyAllWindows()


def start_detection():
    """테스트 에셋 내의 모든 동영상 파일에 대해 객체 감지를 실행"""
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


if __name__ == "__main__":
    # 메인 스레드에서 Tkinter root 창 생성 및 이벤트 처리
    root = tk.Tk()
    root.withdraw()  # 메인 창 숨기기
    root.after(100, process_queue, root)
    root.after(30, process_display_queue)

    # 비디오 객체 감지 처리는 별도 스레드에서 실행
    detection_thread = threading.Thread(target=start_detection, daemon=True)
    detection_thread.start()

    # Tkinter 이벤트 루프 실행 (메인 스레드)
    root.mainloop()
