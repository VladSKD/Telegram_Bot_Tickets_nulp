import io
import qrcode
from PIL import Image, ImageDraw, ImageFont

def create_personalized_ticket(order_id: int, event_title: str, seat_str: str = None) -> io.BytesIO:
    # 1. Завантажуємо базовий шаблон квитка (PNG/JPG)
    # Зберігайте макет у папці проекту, наприклад, "static/ticket_template.png"
    template = Image.open("static/ticket_template.png").convert("RGBA")
    
    # 2. Генеруємо QR-код із даними замовлення
    qr_payload = f"https://your-domain.com/verify?order={order_id}"  # або просто "NULP-{order_id}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(qr_payload)
    qr.make(fit=True)
    
    # Створюємо зображення QR-коду
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    
    # 3. Масштабуємо QR-код під потрібні розміри на шаблоні (наприклад, 250x250 px)
    qr_size = (250, 250)
    qr_img = qr_img.resize(qr_size)
    
    # 4. Накладаємо QR-код на шаблон за координатами (X, Y)
    # Змініть (800, 150) на реальні координати вашої рамки під QR на макеті
    qr_position = (800, 150)
    template.paste(qr_img, qr_position, mask=qr_img)
    
    # (Опціонально) 5. Нанесення тексту (Ряд, Місце, ID) прямо на картинку
    draw = ImageDraw.Draw(template)
    # font = ImageFont.truetype("arial.ttf", size=24) # якщо є файл шрифту
    if seat_str:
        draw.text((100, 450), f"Місце: {seat_str}", fill=(0, 0, 0, 255))
    draw.text((100, 500), f"Замовлення №{order_id}", fill=(100, 100, 100, 255))

    # 6. Зберігаємо підсумкове фото у буфер пам'яті
    buffer = io.BytesIO()
    template.save(buffer, format="PNG")
    buffer.seek(0)
    
    return buffer