
import cv2
import numpy as np
import json



def process_hall_plan(image_path, output_json="coordinates.json"):
    img = cv2.imread(image_path)
    if img is None:
        print("Помилка: Не вдалося завантажити зображення.")
        return

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    coordinates = {
        "yellow_lodges": [],
        "black_pillars": [],
        "available_seats": [],
        "blocked_seats": []
    }

    # 1. ЖОВТІ ЛОЖІ
    lower_yellow = np.array([20, 100, 100])
    upper_yellow = np.array([40, 255, 255])
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        if 20 < cv2.contourArea(cnt) < 2000:
            x, y, w, h = cv2.boundingRect(cnt)
            coordinates["yellow_lodges"].append({"x": x + w//2, "y": y + h//2})

    # 2. ЧОРНІ КОЛОНИ
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 60])
    black_mask = cv2.inRange(hsv, lower_black, upper_black)
    contours, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        if 20 < cv2.contourArea(cnt) < 1000:
            x, y, w, h = cv2.boundingRect(cnt)
            coordinates["black_pillars"].append({"x": x + w//2, "y": y + h//2})

    # 3. МІСЦЯ (Фільтр за габаритами коробки)
    # Шукаємо всі темні/сірі відтінки (відсікаємо білий фон)
    lower_dark = np.array([0, 0, 0])
    upper_dark = np.array([179, 150, 180]) 
    dark_mask = cv2.inRange(hsv, lower_dark, upper_dark)

    # Видаляємо з пошуку ложі та колони, щоб не дублювати
    dark_mask = cv2.bitwise_and(dark_mask, cv2.bitwise_not(yellow_mask))
    dark_mask = cv2.bitwise_and(dark_mask, cv2.bitwise_not(black_mask))

    contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        
        # НАЙГОЛОВНІШИЙ ФІЛЬТР: Місце - це фігура, яка має ширину і висоту від 5 до 25 пікселів
        # (Якщо кружки не знаходить, спробуйте змінити 5 на 3, а 25 на 35)
        if 5 <= w <= 25 and 5 <= h <= 25:
            
            # Перевіряємо, чи це не довга лінія (співвідношення сторін має бути близько 1:1)
            aspect_ratio = float(w) / h
            if 0.7 <= aspect_ratio <= 1.3:
                cx = x + w // 2
                cy = y + h // 2
                
                # Перевірка на закресленість (через щільність пікселів)
                roi = gray[y:y+h, x:x+w]
                _, thresh = cv2.threshold(roi, 120, 255, cv2.THRESH_BINARY_INV)
                fill_ratio = cv2.countNonZero(thresh) / (w * h)
                
                # Якщо об'єкт дуже "заповнений" (бо там лінія закреслення)
                if fill_ratio > 0.65:
                    coordinates["blocked_seats"].append({"x": cx, "y": cy})
                else:
                    coordinates["available_seats"].append({"x": cx, "y": cy})

    # Збереження та вивід
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(coordinates, f, indent=4, ensure_ascii=False)
    
    print(f"Готово! Знайдено:")
    print(f"- Жовтих лож: {len(coordinates['yellow_lodges'])}")
    print(f"- Чорних колон: {len(coordinates['black_pillars'])}")
    print(f"- Доступних місць: {len(coordinates['available_seats'])}")
    print(f"- Закреслених місць: {len(coordinates['blocked_seats'])}")
    
    # Дебаг
    for p in coordinates["yellow_lodges"]: cv2.circle(img, (p['x'], p['y']), 4, (0, 255, 255), -1)
    for p in coordinates["black_pillars"]: cv2.rectangle(img, (p['x']-3, p['y']-3), (p['x']+3, p['y']+3), (0, 0, 0), -1)
    for p in coordinates["available_seats"]: cv2.circle(img, (p['x'], p['y']), 3, (255, 0, 0), -1)
    for p in coordinates["blocked_seats"]: cv2.circle(img, (p['x'], p['y']), 3, (0, 0, 255), -1)
    
    cv2.imshow("Detected Elements", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    process_hall_plan("hall-plan.jpg")