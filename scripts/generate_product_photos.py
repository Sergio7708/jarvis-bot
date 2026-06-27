"""
Генератор фото товаров — создаёт стилизованные изображения для каждого продукта.
Фото сохраняются в product_photos/{id}.jpg и прописываются в local_photo колонку БД.

Запуск: python scripts/generate_product_photos.py [--all] [--missing]
  --all     сгенерировать для всех товаров (даже с file_id)
  --missing (по умолчанию) только для тех, у кого нет фото
"""
import sqlite3
import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BOT_DIR, "bot_data.db")
PHOTOS_DIR = os.path.join(BOT_DIR, "product_photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)

# Цветовые схемы по категориям
CATEGORY_STYLES = {
    1: {"bg": (24, 36, 60), "accent": (216, 177, 90), "icon": "🚜", "name": "Игровая техника"},
    2: {"bg": (23, 16, 55), "accent": (141, 121, 255), "icon": "🧸", "name": "Фигурки"},
    3: {"bg": (35, 17, 27), "accent": (255, 139, 92), "icon": "⚔", "name": "Оружие"},
    4: {"bg": (18, 32, 42), "accent": (124, 231, 176), "icon": "⚙", "name": "Детали и запчасти"},
    5: {"bg": (16, 25, 38), "accent": (97, 215, 255), "icon": "🏠", "name": "Интерьер"},
    6: {"bg": (42, 18, 48), "accent": (255, 123, 200), "icon": "🎭", "name": "Косплей"},
    7: {"bg": (20, 24, 38), "accent": (216, 177, 90), "icon": "📦", "name": "Прочее"},
}

# Поиск шрифта
def find_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/Inter-SemiBold.ttf" if bold else "C:/Windows/Fonts/Inter-Regular.ttf",
        "C:/Windows/Fonts/Inter-Variable.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else None,
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
    return ImageFont.load_default()


def draw_gradient(draw, size, color1, color2):
    """Рисует градиентный фон"""
    w, h = size
    for y in range(h):
        ratio = y / h
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_blur_circle(draw, cx, cy, radius, color, opacity=0.15):
    """Рисует размытое пятно света"""
    alpha = int(255 * opacity)
    for r in range(radius, 0, -1):
        a = alpha * (1 - r / radius)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(color[0], color[1], color[2], int(a))
        )


def generate_product_photo(product, output_path):
    """Создаёт стилизованное фото для товара"""
    W, H = 1024, 1024
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    prod_id, title, price, cat_id = product
    style = CATEGORY_STYLES.get(cat_id, CATEGORY_STYLES[7])

    # Градиентный фон
    bg2 = tuple(min(c + 15, 255) for c in style["bg"])
    draw_gradient(draw, (W, H), style["bg"], bg2)

    # Размытые световые пятна
    draw_blur_circle(draw, 250, 200, 300, style["accent"], 0.12)
    draw_blur_circle(draw, 750, 700, 350, style["accent"], 0.08)
    draw_blur_circle(draw, 512, 400, 500, style["accent"], 0.04)

    # Сетка/паттерн (линии)
    for x in range(0, W, 60):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 8))
    for y in range(0, H, 60):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 8))

    # Большая иконка категории (центрально)
    icon_font = find_font(200)
    if icon_font:
        icon_bbox = draw.textbbox((0, 0), style["icon"], font=icon_font)
        icon_w = icon_bbox[2] - icon_bbox[0]
        icon_h = icon_bbox[3] - icon_bbox[1]
        icon_x = (W - icon_w) // 2
        icon_y = H // 2 - icon_h - 40
        # Ореол за иконкой
        halo_radius = max(icon_w, icon_h) * 1.5
        draw_blur_circle(draw, W // 2, icon_y + icon_h // 2, int(halo_radius), style["accent"], 0.08)
        draw.text((icon_x, icon_y), style["icon"], font=icon_font, fill=(255, 255, 255, 25))

    # Название категории
    cat_font = find_font(24)
    if cat_font:
        cat_text = style["name"].upper()
        cat_bbox = draw.textbbox((0, 0), cat_text, font=cat_font)
        cat_x = (W - (cat_bbox[2] - cat_bbox[0])) // 2
        draw.text((cat_x, 60), cat_text, font=cat_font, fill=style["accent"] + (180,))

    # Название товара
    name_font_size = 42 if len(title) < 20 else 32
    name_font = find_font(name_font_size, bold=True)
    if name_font:
        # Обрезка длинных названий
        display_title = title if len(title) < 40 else title[:37] + "..."
        name_bbox = draw.textbbox((0, 0), display_title, font=name_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_x = (W - name_w) // 2
        # Тень текста
        draw.text((name_x + 2, 462), display_title, font=name_font, fill=(0, 0, 0, 80))
        draw.text((name_x, 460), display_title, font=name_font, fill=(255, 255, 255, 220))

    # Цена
    price_font = find_font(28, bold=True)
    if price_font:
        price_text = f"{price:,} ₽".replace(",", " ")
        price_bbox = draw.textbbox((0, 0), price_text, font=price_font)
        price_x = (W - (price_bbox[2] - price_bbox[0])) // 2
        # Планка цены
        price_text_w = price_bbox[2] - price_bbox[0]
        pill_x1 = price_x - 24
        pill_y1 = 515
        pill_x2 = price_x + price_text_w + 24
        pill_y2 = 515 + (price_bbox[3] - price_bbox[1]) + 16
        draw.rounded_rectangle(
            [pill_x1, pill_y1, pill_x2, pill_y2],
            radius=16,
            fill=style["accent"] + (180,)
        )
        draw.text((price_x, pill_y1 + 8), price_text, font=price_font, fill=(255, 255, 255, 230))

    # Нижняя метка "3D печать на заказ"
    sub_font = find_font(16)
    if sub_font:
        sub_text = "3D печать на заказ"
        sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        sub_x = (W - (sub_bbox[2] - sub_bbox[0])) // 2
        draw.text((sub_x, 640), sub_text, font=sub_font, fill=(255, 255, 255, 80))

    # ID товара (мелко, угол)
    id_font = find_font(14)
    if id_font:
        id_text = f"#{prod_id:04d}"
        draw.text((W - 85, 25), id_text, font=id_font, fill=(255, 255, 255, 40))

    # Конвертируем в RGB и сохраняем JPEG
    rgb_img = Image.new("RGB", (W, H), (0, 0, 0))
    rgb_img.paste(img, (0, 0), img)
    rgb_img.save(output_path, "JPEG", quality=88)
    print(f"  ✓ {prod_id:04d} {title[:30]:30s} → {os.path.basename(output_path)}")


def main():
    generate_all = "--all" in sys.argv

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, price, category_id FROM products WHERE is_active=1")
    products = c.fetchall()

    if not generate_all:
        # Только те, у кого нет фото
        c.execute("SELECT id FROM products WHERE is_active=1 AND (photo_file_id IS NULL OR photo_file_id = '')")
        no_photo_ids = {r[0] for r in c.fetchall()}
        products = [p for p in products if p[0] in no_photo_ids]

    conn.close()

    print(f"Генерация фото для {len(products)} товаров...")
    count = 0
    for i, product in enumerate(products):
        prod_id = product[0]
        output_path = os.path.join(PHOTOS_DIR, f"{prod_id}.jpg")
        if os.path.isfile(output_path) and not generate_all:
            continue
        generate_product_photo(product, output_path)
        count += 1
        if count % 20 == 0:
            print(f"  [{count}/{len(products)}]")

    # Обновляем local_photo в БД
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for product in products:
        prod_id = product[0]
        output_path = os.path.join(PHOTOS_DIR, f"{prod_id}.jpg")
        if os.path.isfile(output_path):
            c.execute("UPDATE products SET local_photo=? WHERE id=?",
                     (output_path, prod_id))
    conn.commit()
    conn.close()

    print(f"\nГотово. Сгенерировано: {count} фото")
    print(f"Всего фото в product_photos/: {len(os.listdir(PHOTOS_DIR))}")


if __name__ == "__main__":
    main()
