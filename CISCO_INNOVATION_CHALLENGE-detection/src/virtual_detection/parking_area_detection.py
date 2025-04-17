import json

def process_occupancy_data(input_data):
    """
    주어진 JSON 데이터에서 ts_exited와 ts_entered의 시간 차이를 계산하고
    3분(180,000밀리초) 이상이면 status=1, 아니면 status=0으로 설정하여 반환합니다.
    """
    # 문자열인 경우 JSON으로 파싱
    if isinstance(input_data, str):
        data = json.loads(input_data)
    else:
        data = input_data
    
    # 결과 객체 초기화
    result = {
        "labels": data.get("label", ""),
        "objects": [],
        "ts": data.get("ts", 0)
    }
    
    # 각 객체에 대해 처리
    for obj in data.get("objects", []):
        ts_entered = obj.get("ts_entered", 0)
        ts_exited = obj.get("ts_exited", 0)
        
        # status 결정
        # ts_exited가 0이면 아직 퇴장하지 않은 것으로 간주하고 status=0
        if ts_exited == 0:
            status = 0
        else:
            # 체류 시간 계산 (밀리초 단위)
            duration = ts_exited - ts_entered
            # 3분(180,000밀리초) 이상이면 status=1, 아니면 status=0
            status = 1 if duration >= 180000 else 0
        
        # 결과 객체에 추가
        result_obj = {
            "object_id": obj.get("object_id", 0),
            "type": obj.get("type", ""),
            "status": status
        }
        result["objects"].append(result_obj)
    
    return result

# 테스트 코드
if __name__ == "__main__":
    # JSON 파일에서 데이터 읽기
    with open("../test_assets/occupancy_data.json", "r") as file:
        example_data = json.load(file)
    
    # 데이터 처리 및 결과 출력
    result = process_occupancy_data(example_data)
    print(json.dumps(result, indent=2))