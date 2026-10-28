import json

def extract_seat_coordinates(input_file, output_file):
    # Відкриваємо оригінальний файл для читання
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    extracted_data = []

    # Перевіряємо наявність потрібних ключів та проходимося по структурі
    if 'data' in data and 'sectors' in data['data']:
        for sector in data['data']['sectors']:
            sector_name = sector.get('name', '')
            
            for row in sector.get('rows', []):
                row_number = row.get('number', '')
                
                for place in row.get('places', []):
                    seat_number = place.get('number', '')
                    x = place.get('x')
                    y = place.get('y')

                    # Формуємо об'єкт лише з необхідними полями
                    extracted_data.append({
                        "sector": sector_name,
                        "row": row_number,
                        "seat": seat_number,
                        "x": x,
                        "y": y
                    })

    # Зберігаємо результат у новий файл з гарним форматуванням (indent=4)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=4)
        
    print(f"Успішно оброблено та збережено {len(extracted_data)} місць у файл {output_file}")

# Запуск скрипта (вкажіть ваші назви файлів)
if __name__ == "__main__":
    extract_seat_coordinates('kpnta.json', 'simplified_seats.json')