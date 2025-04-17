#!/usr/bin/env python3
import os
import sys
import json
import requests
from datetime import datetime

if len(sys.argv) < 3:
    print("Usage: python3 detection_upload.py <image_path> <json_path>")
    sys.exit(1)

image_path = sys.argv[1]
json_path = sys.argv[2]

if not os.path.exists(json_path):
    print(f"JSON file not found: {json_path}")
    sys.exit(1)
with open(json_path, "r") as f:
    detection_data = json.load(f)

if isinstance(detection_data, list) and len(detection_data) > 0:
    detection = detection_data[0]
    object_id = detection.get("object_id", "정보 없음")
    lat = detection.get("lat", "정보 없음")
    lng = detection.get("lng", "정보 없음")
    timestamp_str = detection.get("timestamp", "정보 없음")
    
   
    lat_formatted = f"{float(lat):.6f}" if lat != "정보 없음" else lat
    lng_formatted = f"{float(lng):.6f}" if lng != "정보 없음" else lng

   
    try:
        dt = datetime.fromisoformat(timestamp_str)
        timestamp_formatted = dt.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
    except Exception:
        timestamp_formatted = timestamp_str

    message_text = (
        "킥보드 주차 위반이 발생하였습니다!\n"
        f"object_id: {object_id}\n"
        f"위도: {lat_formatted}\n"
        f"경도: {lng_formatted}\n"
        f"시간: {timestamp_formatted}"
    )
else:
    message_text = "킥보드 주차 위반 정보가 없습니다."

creds_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../assets/webex_api_key.json")
if not os.path.exists(creds_file_path):
    print(f"Credentials file not found: {creds_file_path}")
    sys.exit(1)

with open(creds_file_path, "r") as f:
    creds = json.load(f)
WEBEX_BOT_TOKEN = creds.get("BOT_API_KEY")
WEBEX_ROOM_ID = creds.get("ROOM_ID")
if not WEBEX_BOT_TOKEN or not WEBEX_ROOM_ID:
    print("BOT_API_KEY or ROOM_ID not found in credentials file.")
    sys.exit(1)

url = "https://webexapis.com/v1/messages"
headers = {
    "Authorization": f"Bearer {WEBEX_BOT_TOKEN}"
}

data_payload = {
    "roomId": WEBEX_ROOM_ID,
    "text": message_text
}
response = requests.post(url, headers=headers, json=data_payload)

if response.status_code in (200, 201):
    print("Webex text message sent successfully!")
    print(json.dumps(response.json(), indent=2))
else:
    print("Failed to send Webex text message. Response:", response.text)

if os.path.exists(image_path):
    with open(image_path, "rb") as image_file:
        data_payload_file = {
            "roomId": WEBEX_ROOM_ID,
            "text": "킥보드 주차 위반 이미지 첨부"
        }
        response_file = requests.post(url, headers={"Authorization": f"Bearer {WEBEX_BOT_TOKEN}"}, data=data_payload_file, files={"files": image_file})
        if response_file.status_code in (200, 201):
            print("Webex image message sent successfully!")
            print(json.dumps(response_file.json(), indent=2))
        else:
            print("Failed to send Webex image message. Response:", response_file.text)
else:
    print("Image file not found; image message not sent.")
