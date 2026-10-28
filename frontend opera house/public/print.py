import json
import matplotlib.pyplot as plt

# Завантаження даних
with open('simplified_seats.json', 'r', encoding='utf-8') as f:
    seats = json.load(f)

# Витягуємо координати
x = [seat['x'] for seat in seats]
y = [seat['y'] for seat in seats] 

plt.figure(figsize=(12, 8))
plt.scatter(x, y, s=15, alpha=0.8)
plt.gca().invert_yaxis() # Інвертуємо Y, щоб сцена (0,0) була зверху/зліва
plt.title('Схема місць')
plt.xlabel('X (пікселі)')
plt.ylabel('Y (пікселі)')
plt.axis('equal') # Зберігаємо пропорції
plt.show()