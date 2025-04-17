from django.shortcuts import render
import json
import math
import base64
import io
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Event, Camera, User  # DetectionEvent 대신 Event를 임포트
from datetime import datetime
from PIL import Image
from ultralytics import YOLO

@csrf_exempt
def register_user(request):
    if request.method == 'OPTIONS':
        response = HttpResponse(status=200)
        response['Allow'] = 'POST, OPTIONS'
        return response
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            name = "abc"
            email = payload.get('email')
            
            # 필수 값 검증
            if not name:
                return JsonResponse({'status': 'error', 'message': 'name is missing'}, status=400)
            if not email:
                return JsonResponse({'status': 'error', 'message': 'email is missing'}, status=400)
            
            # email을 통해 사용자가 이미 존재하는지 조회
            try:
                user = User.objects.get(email=email)
                # 이미 등록된 경우: 아무 동작도 하지 않고 정보를 반환
                return JsonResponse({
                    'status': 'success', 
                    'message': 'User already registered', 
                    'user': {
                        'name': user.name,
                        'email': user.email,
                        'reward': user.reward
                    }
                }, status=200)
            except User.DoesNotExist:
                # 등록되지 않은 경우: User를 생성 (reward는 기본값 0)
                user = User(name=name, email=email, reward=0)
                user.save()
                return JsonResponse({
                    'status': 'success', 
                    'message': 'User registered successfully', 
                    'user': {
                        'name': user.name,
                        'email': user.email,
                        'reward': user.reward
                    }
                }, status=200)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'invalid method'}, status=405)

@csrf_exempt
def request_reward(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)

            print(payload)

            # 요청 데이터에서 email, timestamp, 위도, 경도 값 추출
            email = payload.get('email')
            timestamp_str = payload.get('timestamp')
            req_lat = payload.get('lat')
            req_lng = payload.get('lng')
            
            
            if not email:
                return JsonResponse({'status': 'error', 'message': 'email is missing'}, status=400)
            if not timestamp_str:
                return JsonResponse({'status': 'error', 'message': 'timestamp is missing'}, status=400)
            if req_lat is None or req_lng is None:
                return JsonResponse({'status': 'error', 'message': 'lat/lng is missing'}, status=400)

            # 사용자를 email로 찾음
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'User not found for provided email'}, status=404)

            # ISO 포맷 timestamp 파싱 (UTC 기준)
            request_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # 가장 가까운 카메라 찾기 (위치 기반)
            from math import sqrt
            cameras = list(Camera.objects.exclude(lat__isnull=True, lng__isnull=True))
            if not cameras:
                return JsonResponse({'status': 'error', 'message': 'No cameras with location data found'}, status=400)

            nearest_camera = None
            min_distance = None
            for cam in cameras:
                dist = sqrt((cam.lat - req_lat)**2 + (cam.lng - req_lng)**2)
                if min_distance is None or dist < min_distance:
                    min_distance = dist
                    nearest_camera = cam

            if not nearest_camera:
                return JsonResponse({'status': 'error', 'message': 'No nearest camera found'}, status=400)

            # Event 모델에서 타임스탬프가 요청 시각보다 이전인 데이터 조회
            event_records = Event.objects.filter(
                camera=nearest_camera,
                timestamp__lte=request_timestamp
            ).order_by('-timestamp')

            if not event_records.exists():
                return JsonResponse({'status': 'error', 'message': 'No historical data for the nearest camera'}, status=400)

            latest_event = event_records.first()
            # JSON 형식의 payload가 리스트라면 해당 리스트의 길이로 판단 (감지된 객체 수)
            latest_count = len(latest_event.payload) if isinstance(latest_event.payload, list) else 0

            # 감지된 객체가 하나 이상이면 보상 실패, 아니면 성공
            reward = 'failed' if latest_count >= 1 else 'success'

            # 성공일 경우 사용자의 reward 값에 10점을 추가
            if reward == 'success':
                user.reward += 10
                user.save()

            # 응답에 성공/실패 여부와 현재 유저 reward 값을 포함
            return JsonResponse({'status': 'success', 'return': reward, 'reward': user.reward}, status=200)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'invalid method'}, status=405)

@csrf_exempt
def readjust(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            lat = payload.get('lat')
            lng = payload.get('lng')
            bearing = payload.get('alpha')
            distance = payload.get('distance')
            timestamp_str = payload.get('timestamp')
            email = payload.get('email')
            image_data = payload.get('image_data')  # Base64 인코딩된 이미지 데이터

            # 필수 값 검증
            if not timestamp_str:
                return JsonResponse({'status': 'error', 'message': 'timestamp is missing'}, status=400)
            if not email:
                return JsonResponse({'status': 'error', 'message': 'email is missing'}, status=400)
            if image_data is None:
                return JsonResponse({'status': 'error', 'message': 'image_data is missing'}, status=400)

            # ISO 포맷 timestamp 파싱 (UTC 기준)
            request_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # 사용자 조회 (email 기반)
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)

            # 재조정을 위한 대상 위치 계산 (destination_point 함수 사용)
            object_lat, object_lng = destination_point(lat, lng, bearing, distance)

            # --- 이미지 데이터 처리 및 ultralytics YOLO 모델 추론 ---
            # Base64 디코딩 후 PIL Image 객체 생성
            img_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(img_bytes)).convert('RGB')

            # ultralytics YOLO 모델 로드 (이미 로드한 모델을 재사용하거나, 매 호출마다 로드 가능)
            # 모델 파일 경로는 예시와 같이 "../../detection/models/model.pt"로 지정함.
            model = YOLO("../../detection/models/model.pt")
            results = model(image, verbose=False)

            # 객체 감지 결과에서 "kb" 클래스 추출
            found_kb = False
            # 아래 방식은 예시 코드에서 "kb" 클래스를 추출하는 로직과 동일하게, 클래스 인덱스 1을 kb로 간주
            for r in results:
                for box in r.boxes:
                    cls_index = int(box.cls.item())
                    if cls_index == 1:  # kb 클래스가 index 1이라고 가정
                        found_kb = True
                        break
                if found_kb:
                    break

            # 1차 성공 여부: "kb" 클래스가 검출되면 success, 아니면 failed
            if found_kb:
                reward_result = 'success'
                user.reward += 10  # 성공 시 사용자 reward 10점 추가
                user.save()
            else:
                reward_result = 'failed'

            return JsonResponse({
                'status': 'success',
                'return': reward_result,
                'reward': user.reward  # 현재 누적 reward 점수 포함
            }, status=200)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'invalid method'}, status=405)
    
@csrf_exempt 
def monitor_page(request):
    # 최근 10개의 Event 데이터를 시간 내림차순으로 조회
    events = Event.objects.all().order_by('-timestamp')[:10]
    context = {
        'events': events,
    }
    return render(request, 'monitor.html', context)


def destination_point(lat, lng, bearing, distance):
    R = 6371000  # 지구 반지름 (미터)
    lat1 = math.radians(lat)
    lng1 = math.radians(lng)
    bearing_rad = math.radians(bearing)
    
    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance / R) +
        math.cos(lat1) * math.sin(distance / R) * math.cos(bearing_rad)
    )
    
    lng2 = lng1 + math.atan2(
        math.sin(bearing_rad) * math.sin(distance / R) * math.cos(lat1),
        math.cos(distance / R) - math.sin(lat1) * math.sin(lat2)
    )
    
    return math.degrees(lat2), math.degrees(lng2)