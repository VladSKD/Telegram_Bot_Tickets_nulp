import json
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

# Завантажуємо зображення та дані
img = mpimg.imread('hall-plan.jpg')
with open('simplified_seats.json', 'r', encoding='utf-8') as f:
    seats = json.load(f)

x = [seat['x'] for seat in seats]
y = [seat['y'] for seat in seats]

fig, ax = plt.subplots(figsize=(15, 10))

# СЕКРЕТ ТУТ: Задаємо межі для картинки [x_min, x_max, y_max, y_min]
# Зверни увагу: y_max і y_min перевернуті (3400, 0), щоб нуль був зверху
ax.imshow(img, extent=[0, 4550, 3350, 0], aspect='auto')

# Накладаємо точки
ax.scatter(x, y, color='red', s=10, alpha=0.6)

plt.title('Перевірка координат на плані залу (Виправлено)')
plt.axis('off')

# Зберігаємо у файл, щоб не було проблем з вікном Matplotlib
plt.savefig('overlay_result.png', dpi=300, bbox_inches='tight')
print("Готово! Перевір файл overlay_result.png")