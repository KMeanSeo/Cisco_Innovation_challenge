import requests
import json
import sys
import os

creds_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../assets/webex_api_key.json")
if not os.path.exists(creds_file_path):
    print(f"Credentials file not found: {creds_file_path}")
    sys.exit(1)

with open(creds_file_path, "r") as f:
    creds = json.load(f)
WEBEX_API_TOKEN = creds.get("API_KEY")
if not WEBEX_API_TOKEN:
    print("API_KEY not found in credentials file.")
    sys.exit(1)

USER_EMAIL = creds.get("USER_EMAIL")
BOT_EMAIL = creds.get("BOT_EMAIL")
if not USER_EMAIL or not BOT_EMAIL:
    print("USER_EMAIL or BOT_EMAIL not found in credentials file.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {WEBEX_API_TOKEN}",
    "Content-Type": "application/json"
}

create_room_url = "https://webexapis.com/v1/rooms"
room_title = "API Test Room"
room_payload = {"title": room_title}

create_room_response = requests.post(create_room_url, headers=headers, data=json.dumps(room_payload))
if create_room_response.status_code not in (200, 201):
    print("Room creation failed:", create_room_response.text)
    sys.exit(1)
room_info = create_room_response.json()
room_id = room_info.get("id")
print("Room created successfully. Room ID:", room_id)

creds["ROOM_ID"] = room_id
with open(creds_file_path, "w") as f:
    json.dump(creds, f, indent=2)
print("ROOM_ID updated in credentials file.")

membership_url = "https://webexapis.com/v1/memberships"

user_payload = {"roomId": room_id, "personEmail": USER_EMAIL}
invite_user_response = requests.post(membership_url, headers=headers, data=json.dumps(user_payload))
if invite_user_response.status_code not in (200, 201):
    error_resp = invite_user_response.json()
    # If the error indicates that the user is already a participant, treat it as success.
    if "User is already a participant" in invite_user_response.text:
        print("User is already a participant in the room.")
    else:
        print("User invitation failed:", invite_user_response.text)
else:
    print("User invited successfully to the room.")

bot_payload = {"roomId": room_id, "personEmail": BOT_EMAIL}
invite_bot_response = requests.post(membership_url, headers=headers, data=json.dumps(bot_payload))
if invite_bot_response.status_code not in (200, 201):
    print("Bot invitation failed:", invite_bot_response.text)
else:
    print("Bot invited successfully to the room.")
