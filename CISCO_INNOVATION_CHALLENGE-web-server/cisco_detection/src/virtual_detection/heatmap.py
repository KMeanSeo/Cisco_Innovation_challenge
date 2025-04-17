import cv2
import numpy as np

def get_color_mask(hsv, lower, upper):
    return cv2.inRange(hsv, lower, upper)

def preprocess_mask(mask):
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask

def get_polygons(mask, epsilon_factor=0.02):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygons = []
    for contour in contours:
        if cv2.contourArea(contour) > 100:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon_factor * peri, True)
            polygons.append(approx)
    return polygons

def is_contour_inside(inner, outer):
    outer = outer.astype(np.float32)
    for point in inner:
        x, y = point[0]
        if cv2.pointPolygonTest(outer, (float(x), float(y)), False) < 0:
            return False
    return True

def draw_polygons(image, polygons, color, label):
    for poly in polygons:
        cv2.polylines(image, [poly], isClosed=True, color=color, thickness=2)
        for point in poly:
            x, y = point[0]
            cv2.circle(image, (x, y), 3, color, -1)
    print(f"{label} polygon(s): {len(polygons)}")

def find_and_draw(image_path):
    image = cv2.imread(image_path)
    if image is None:
        print("이미지를 불러올 수 없습니다.")
        return

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 색상 범위 정의
    red1 = (np.array([0, 120, 100]), np.array([10, 255, 255]))
    red2 = (np.array([170, 120, 100]), np.array([180, 255, 255]))
    orange = (np.array([11, 120, 100]), np.array([25, 255, 255]))
    yellow = (np.array([26, 120, 100]), np.array([35, 255, 255]))

    # 마스크 생성
    mask_red = cv2.bitwise_or(get_color_mask(hsv, *red1), get_color_mask(hsv, *red2))
    mask_orange = get_color_mask(hsv, *orange)
    mask_yellow = get_color_mask(hsv, *yellow)

    # 전처리
    mask_red = preprocess_mask(mask_red)
    mask_orange = preprocess_mask(mask_orange)
    mask_yellow = preprocess_mask(mask_yellow)

    # 포함 마스크
    mask_orange_total = cv2.bitwise_or(mask_orange, mask_red)
    mask_yellow_total = cv2.bitwise_or(mask_yellow, mask_orange_total)

    # 다각형 추출
    red_polygons = get_polygons(mask_red)
    orange_polygons = get_polygons(mask_orange_total)
    yellow_polygons = get_polygons(mask_yellow_total)

    result = image.copy()
    draw_polygons(result, yellow_polygons, (0, 0, 0), "Yellow (total)")
    draw_polygons(result, orange_polygons, (0, 165, 255), "Orange (total)")
    draw_polygons(result, red_polygons, (0, 0, 255), "Red")

    for orange_poly in orange_polygons:
        if not any(is_contour_inside(orange_poly, yellow_poly) for yellow_poly in yellow_polygons):
            cv2.polylines(result, [orange_poly], isClosed=True, color=(255, 0, 255), thickness=2)
            print("노랑 안에 포함되지 않은 주황 다각형 감지")

    for red_poly in red_polygons:
        if not any(is_contour_inside(red_poly, orange_poly) for orange_poly in orange_polygons):
            cv2.polylines(result, [red_poly], isClosed=True, color=(255, 0, 0), thickness=2)
            print("주황 안에 포함되지 않은 빨강 다각형 감지")

    # 여집합 마스크: 노랑 - (빨강 + 주황)
    red_or_orange_mask = cv2.bitwise_or(mask_red, mask_orange)
    yellow_only_mask = cv2.bitwise_and(mask_yellow, cv2.bitwise_not(red_or_orange_mask))
    yellow_only_mask = preprocess_mask(yellow_only_mask)

    # 여집합만 남기고 나머지 검정색으로 칠한 이미지 생성
    filtered_result = cv2.bitwise_and(image, image, mask=yellow_only_mask)

    # 여집합 다각형 표시 (선택적 디버깅용)
    yellow_only_polygons = get_polygons(yellow_only_mask)
    draw_polygons(filtered_result, yellow_only_polygons, (0, 255, 0), "Yellow-Only (filtered)")

    try:
        cv2.imshow("Result", result)
        cv2.imshow("Filtered Yellow", filtered_result)
        print("ESC 키로 종료하거나 Ctrl+C로 중단할 수 있습니다.")
        while True:
            if cv2.waitKey(100) == 27:
                break
    except KeyboardInterrupt:
        print("\nCtrl+C 감지. 종료합니다.")
    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    find_and_draw("../test_assets/heatmap_example.png")
