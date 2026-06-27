"""
Админ-панель: управление заказами, товарами, категориями, репостером,
редактирование, фотоотчёты, бан-лист, бэкап, уведомления клиентам
"""
import os
import time
import logging
from aiogram import Router, types, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from states import (
    AddProductFSM, AddCategoryFSM, EditProductFSM,
    EditCategoryFSM, PhotoReportFSM
)
from db import (
    get_orders, get_orders_count, get_order, update_order_status, get_categories, add_category,
    delete_category, get_products, get_product, add_product, delete_product,
    update_product, get_stats, backup_db, get_order_photos, add_order_photo,
    get_banned_users, ban_user, unban_user, get_subscribers,
    get_user_orders_count,
)
from keyboards import (
    admin_order_nav, order_status_actions, cancel_kb,
    catalog_categories, main_menu
)
from buttons import text_match, html_escape, BTN_ORDERS, BTN_ADD_PRODUCT, BTN_CATEGORIES, BTN_STATS, BTN_REPOSTER, BTN_PHOTO, BTN_BACKUP, BTN_BANLIST, BTN_BACK, BTN_CANCEL
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()

# Папка для локальных фото товаров
BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCT_PHOTOS_DIR = os.path.join(BOT_DIR, "product_photos")
os.makedirs(PRODUCT_PHOTOS_DIR, exist_ok=True)


def is_admin(user_id):
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Доступ запрещён.")
        return
    await message.answer(
        "<b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=main_menu(user_id=message.from_user.id), parse_mode="HTML"
    )


# ========================
# ЗАКАЗЫ
# ========================

@router.message(text_match(BTN_ORDERS))
async def show_orders(message: Message):
    if not is_admin(message.from_user.id):
        return
    _order_filters.pop(message.chat.id, None)
    try:
        await show_orders_page(message, 0)
    except Exception as e:
        logger.error(f"show_orders error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {e}")


async def show_orders_page(message: Message, page=0, status_filter=None):
    total = get_orders_count(status_filter)
    if total == 0:
        await message.answer("Заказов пока нет.")
        return
    page = max(0, min(page, total - 1))
    orders = get_orders(status=status_filter, limit=1, offset=page)
    if not orders:
        await message.answer("Заказов пока нет.")
        return
    o = orders[0]
    status_emoji = {"new": "🆕", "accepted": "📋", "working": "🔄", "printing": "🖨️", "shipped": "📦", "completed": "✅", "cancelled": "❌"}
    status_text = {"new": "Новый", "accepted": "Принят", "working": "В работе", "printing": "В печати", "shipped": "Отгружен", "completed": "Выполнен", "cancelled": "Отменён"}

    # Инфо о клиенте
    from db import get_user_orders_count
    customer_orders = get_user_orders_count(o['user_id'])

    text = (
        f"<b>Заказ #{o['id']}</b>\n\n"
        f"👤 <b>Клиент:</b> {html_escape(o['username'])} (id:{o['user_id']})\n"
        f"📦 <b>Заказов клиента:</b> {customer_orders}\n"
        f"🖼️ <b>Модель:</b> {html_escape(o['product'])}\n"
        f"🧵 <b>Материал:</b> {html_escape(o['material'])}\n"
        f"🎨 <b>Цвет:</b> {html_escape(o['color'])}\n"
        f"🔢 <b>Количество:</b> {o['qty']}\n"
        f"📞 <b>Контакт:</b> {html_escape(o['contact'])}\n"
    )
    if o['total_price']:
        text += f"💵 <b>Сумма:</b> {o['total_price']:,}₽\n"
    if o['comment']:
        text += f"💬 <b>Комментарий:</b> {html_escape(o['comment'])}\n"
    text += f"\n{status_emoji.get(o['status'], '')} <b>Статус:</b> {status_text.get(o['status'], o['status'])}\n{o['date']}"
    await message.answer(text, reply_markup=admin_order_nav(page, total, status_filter), parse_mode="HTML")


# Хранилище текущего фильтра для каждого чата
_order_filters = {}

@router.callback_query(F.data.startswith("oadmin_"))
async def admin_order_nav_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    parts = callback.data.split("_")
    page = int(parts[1])
    status_filter = _order_filters.get(callback.message.chat.id)
    await show_orders_page(callback.message, page, status_filter)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("ofilter_"))
async def admin_order_filter_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    status = callback.data.split("_", 1)[1]
    if status == 'all':
        status = None
    _order_filters[callback.message.chat.id] = status
    await show_orders_page(callback.message, 0, status)
    await callback.answer()


@router.callback_query(F.data.startswith("ostatus_"))
async def set_order_status(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    parts = callback.data.split("_")
    order_id = int(parts[1])
    new_status = parts[2]
    update_order_status(order_id, new_status)
    status_names = {"accepted": "Принят", "working": "В работе", "printing": "В печати", "shipped": "Отгружен", "completed": "Выполнен", "cancelled": "Отменён"}
    await callback.message.edit_text(callback.message.text.html_text + f"\n\nСтатус изменён на: <b>{status_names.get(new_status, new_status)}</b>", parse_mode="HTML")
    await callback.answer(f"Статус -> {status_names.get(new_status, new_status)}")
    order = get_order(order_id)
    if order and order["user_id"]:
        try:
            await bot.send_message(chat_id=order["user_id"], text=f"<b>Статус заказа #{order_id}</b>\n\n<b>{html_escape(order['product'])}</b>\nНовый статус: <b>{status_names.get(new_status, new_status)}</b>\n\nСпасибо за ваш заказ!", parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to notify user {order['user_id']}: {e}")


# ========================
# ДОБАВЛЕНИЕ ТОВАРА
# ========================

@router.message(text_match(BTN_ADD_PRODUCT))
async def start_add_product(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    categories = get_categories()
    if not categories:
        await message.answer("Сначала добавьте категорию через «Категории».")
        return
    await state.set_state(AddProductFSM.choose_category)
    await message.answer("<b>Добавление товара</b>\n\nШаг 1/5 — Выберите категорию:", reply_markup=catalog_categories(categories), parse_mode="HTML")


@router.callback_query(AddProductFSM.choose_category, F.data.startswith("cat_"))
async def add_product_cat(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductFSM.enter_title)
    await callback.message.edit_text("Шаг 2/5 — Введите <b>название</b> товара:", parse_mode="HTML")
    await callback.answer()


@router.message(AddProductFSM.enter_title)
async def add_product_title(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(AddProductFSM.enter_desc)
    await message.answer("Шаг 3/5 — Введите <b>описание</b> товара (или «-»):", reply_markup=cancel_kb(), parse_mode="HTML")


@router.message(AddProductFSM.enter_desc)
async def add_product_desc(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    desc = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(desc=desc)
    await state.set_state(AddProductFSM.enter_price)
    await message.answer("Шаг 4/5 — Введите <b>цену</b> в рублях (только число, или 0):", reply_markup=cancel_kb(), parse_mode="HTML")


@router.message(AddProductFSM.enter_price)
async def add_product_price(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число (например: 1500). Или 0 если цена по запросу.")
        return
    await state.update_data(price=price)
    await state.set_state(AddProductFSM.upload_photo)
    await message.answer("Шаг 5/5 — Отправьте <b>фото</b> товара (или «-» без фото):", reply_markup=cancel_kb(), parse_mode="HTML")


@router.message(AddProductFSM.upload_photo)
async def add_product_photo(message: Message, state: FSMContext, bot: Bot):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    photo = ""
    if message.photo:
        photo = message.photo[-1].file_id
        try:
            file = await bot.get_file(photo)
            local_name = f"temp_{message.from_user.id}_{int(time.time())}.jpg"
            local_path = os.path.join(PRODUCT_PHOTOS_DIR, local_name)
            await bot.download_file(file.file_path, local_path)
            await state.update_data(temp_photo_path=local_path)
        except Exception as e:
            logger.warning(f"Не удалось сохранить фото локально: {e}")
    elif message.text and message.text.strip() == "-":
        photo = ""
    else:
        await message.answer("Отправьте фото или «-» чтобы пропустить.")
        return
    await state.update_data(photo=photo)
    await state.set_state(AddProductFSM.confirm)
    await message.answer("Шаг 6/6 — Укажите <b>количество на складе</b> (число, или -1 если не ограничено):", reply_markup=cancel_kb(), parse_mode="HTML")


@router.message(AddProductFSM.confirm)
async def add_product_confirm(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    try:
        stock = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число (например: 10) или -1 если не ограничено.")
        return
    data = await state.get_data()
    prod_id = add_product(cat_id=data["category_id"], title=data["title"], desc=data.get("desc", ""), price=data.get("price", 0), photo=data.get("photo", ""), stock=stock)

    temp_path = data.get("temp_photo_path")
    if temp_path and os.path.isfile(temp_path):
        try:
            final_name = f"{prod_id}.jpg"
            final_path = os.path.join(PRODUCT_PHOTOS_DIR, final_name)
            os.rename(temp_path, final_path)
            update_product(prod_id, local_photo=final_path)
        except Exception as e:
            logger.warning(f"Не удалось переименовать временное фото для товара #{prod_id}: {e}")

    await message.answer(f"✅ Товар <b>«{html_escape(data['title'])}»</b> добавлен в каталог!\nЗапас: {str(stock) if stock >= 0 else 'не ограничен'}", reply_markup=main_menu(user_id=message.from_user.id), parse_mode="HTML")
    await state.clear()


# ========================
# РЕДАКТИРОВАНИЕ ТОВАРА
# ========================

@router.message(Command("edit_product"))
async def cmd_edit_product(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    products = get_products()
    if not products:
        await message.answer("Нет товаров для редактирования.")
        return
    text = "<b>Редактирование товара</b>\n\nОтправьте ID товара:\n\n"
    for p in products[:20]:
        stock_str = f" [{p['stock']} шт.]" if p.get('stock', -1) >= 0 else ""
        text += f"#{p['id']} {html_escape(p['title'])} — {p['price']}₽{stock_str}\n"
    await message.answer(text, parse_mode="HTML")
    await state.set_state(EditProductFSM.choose_product)


@router.message(EditProductFSM.choose_product)
async def edit_choose_product(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    try:
        prod_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите ID товара (число).")
        return
    product = get_product(prod_id)
    if not product:
        await message.answer("Товар с таким ID не найден.")
        return
    await state.update_data(product_id=prod_id)
    await state.set_state(EditProductFSM.enter_title)
    await message.answer(
        f"<b>Редактирование товара #{prod_id}</b>\n\n"
        f"Текущее название: {html_escape(product['title'])}\n"
        f"Введите новое название (или «-» чтобы оставить):",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )


# ========================
# КАТЕГОРИИ
# ========================

@router.message(text_match(BTN_CATEGORIES))
async def show_categories_menu(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        cats = get_categories()
        text = "<b>Управление категориями</b>\n\n"
        if cats:
            for c in cats:
                text += f"{c['emoji'] or ''} {c['name']}\n"
            text += f"\nВсего: {len(cats)} категорий\n"
        else:
            text += "Категорий пока нет.\n"
        text += "\n/add_category — добавить категорию\n/del_category (ID) — удалить категорию"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"categories error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {e}")


@router.message(Command("add_category"))
async def add_category_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddCategoryFSM.enter_name)
    await message.answer("Введите название категории:", reply_markup=cancel_kb())


@router.message(AddCategoryFSM.enter_name)
async def add_category_name(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddCategoryFSM.enter_emoji)
    await message.answer("Введите символ для категории (или «-»):", reply_markup=cancel_kb())


@router.message(AddCategoryFSM.enter_emoji)
async def add_category_emoji(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    emoji = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(emoji=emoji)
    await state.set_state(AddCategoryFSM.enter_desc)
    await message.answer("Введите описание категории (или «-»):", reply_markup=cancel_kb())


@router.message(AddCategoryFSM.enter_desc)
async def add_category_desc(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    desc = "" if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    add_category(name=data["name"], emoji=data.get("emoji", ""), desc=desc)
    await message.answer(f"Категория <b>«{html_escape(data['name'])}»</b> добавлена!", reply_markup=main_menu(user_id=message.from_user.id), parse_mode="HTML")
    await state.clear()


@router.message(Command("del_category"))
async def delete_category_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        cat_id = int(message.text.split(maxsplit=1)[1])
        delete_category(cat_id)
        await message.answer(f"Категория #{cat_id} удалена вместе с товарами.")
    except (IndexError, ValueError):
        cats = get_categories()
        text = "Использование: /del_category <ID>\n\n"
        for c in cats:
            text += f"{c['id']}: {c['emoji']} {c['name']}\n"
        await message.answer(text)


# ========================
# СТАТИСТИКА
# ========================

@router.message(text_match(BTN_STATS))
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        s = get_stats()
        emoji = {"orders_new": "🆕", "orders_active": "🔄", "orders_done": "✅", "orders_cancelled": "❌"}
        text = (
            f"📊 <b>Дашборд студии</b>\n\n"
            f"📁 Категории: <b>{s['categories']}</b>\n"
            f"🏷️ Товары: <b>{s['products']}</b>\n"
            f"👥 Подписчики: <b>{s['subscribers']}</b>\n\n"
            f"<b>📦 Заказы</b>\n"
            f"  {emoji['orders_new']} Новых: <b>{s['orders_new']}</b>\n"
            f"  {emoji['orders_active']} В работе: <b>{s['orders_active']}</b>\n"
            f"  {emoji['orders_done']} Отгружено: <b>{s['orders_done']}</b>\n"
            f"  {emoji['orders_cancelled']} Отменено: <b>{s['orders_cancelled']}</b>\n"
            f"  📋 Всего: <b>{s['orders_total']}</b>\n\n"
            f"💰 <b>Выручка (отгружено):</b> {s['revenue']:,}₽\n"
        )
        if s['top_products']:
            text += "\n<b>🏆 Популярные модели:</b>\n"
            for i, (n, c) in enumerate(s['top_products'], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"  {i}."
                text += f"  {medal} {html_escape(n)} — {c} заказов\n"
        import config
        reposter_status = "✅ включён" if config.REPOSTER_ENABLED else "❌ выключен"
        text += f"\n🔄 <b>Репостер:</b> {reposter_status}"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"show_stats error: {e}", exc_info=True)
        await message.answer(f"Ошибка: {e}")


# ========================
# РЕПОСТЕР
# ========================

@router.message(text_match(BTN_REPOSTER))
async def show_reposter_status(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        import config
        status_text = "Включён" if config.REPOSTER_ENABLED else "Выключен"
        text = f"<b>Репостер</b>\n\nИсточник: @stlmodelforprint\nКанал: @D3ModelerDesigner\nИнтервал: {config.REPOSTER_INTERVAL} сек\nСтатус: {status_text}\n\n/reposter_on — включить\n/reposter_off — выключить"
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"reposter error: {e}")
        await message.answer(f"Ошибка: {e}")


@router.message(Command("reposter_on"))
async def reposter_on(message: Message):
    if not is_admin(message.from_user.id):
        return
    import config
    config.REPOSTER_ENABLED = True
    await message.answer("Репостер включён.")


@router.message(Command("reposter_off"))
async def reposter_off(message: Message):
    if not is_admin(message.from_user.id):
        return
    import config
    config.REPOSTER_ENABLED = False
    await message.answer("Репостер выключен.")


# ========================
# ФОТООТЧЁТ
# ========================

@router.message(text_match(BTN_PHOTO))
async def cmd_photo_report(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(PhotoReportFSM.enter_caption)
    await message.answer("<b>Фотоотчёт по заказу</b>\n\nВведите номер заказа, затем отправьте фото:", reply_markup=cancel_kb(), parse_mode="HTML")


@router.message(PhotoReportFSM.enter_caption)
async def photo_report_input(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        return
    try:
        order_id = int(message.text.strip())
        order = get_order(order_id)
        if not order:
            await message.answer("Заказ не найден.")
            return
    except ValueError:
        await message.answer("Введите ID заказа (число).")
        return
    await state.update_data(photo_order_id=order_id)
    await message.answer(f"Заказ #{order_id}. Теперь отправьте фото с подписью:", reply_markup=cancel_kb())
    await state.set_state(PhotoReportFSM.confirm)


@router.message(PhotoReportFSM.confirm)
async def photo_report_send(message: Message, state: FSMContext, bot: Bot):
    if message.text == BTN_CANCEL:
        await state.clear()
        return
    data = await state.get_data()
    order_id = data.get("photo_order_id")
    order = get_order(order_id)
    if not order or not message.photo:
        await message.answer("Ошибка.")
        return
    photo = message.photo[-1].file_id
    caption = message.caption or "Фотоотчёт по заказу"
    add_order_photo(order_id, message.from_user.id, photo, caption)
    if order["user_id"]:
        try:
            await bot.send_photo(chat_id=order["user_id"], photo=photo, caption=f"<b>Фотоотчёт по заказу #{order_id}</b>\n\n{html_escape(caption)}", parse_mode="HTML")
            await message.answer(f"Фото отправлено (заказ #{order_id}).", reply_markup=main_menu(user_id=message.from_user.id))
        except Exception as e:
            await message.answer(f"Фото сохранено, клиент недоступен: {e}", reply_markup=main_menu(user_id=message.from_user.id))
    else:
        await message.answer("Фото сохранено.", reply_markup=main_menu(user_id=message.from_user.id))
    await state.clear()


# ========================
# ЗАГРУЗКА ФОТО В КАРТОЧКУ ТОВАРА (локально)
# ========================

@router.message(Command("product_photo"))
async def cmd_product_photo(message: Message, bot: Bot):
    """Админ отправляет фото с ID товара в подписи, бот скачивает и сохраняет локально"""
    if not is_admin(message.from_user.id):
        return
    if not message.photo or not message.caption:
        await message.answer("Отправьте фото с ID товара в подписи.\n\nПример: отправьте фото, а в подписи напишите 123")
        return
    try:
        product_id = int(message.caption.strip())
    except ValueError:
        await message.answer("В подписи должен быть ID товара (число).")
        return
    product = get_product(product_id)
    if not product:
        await message.answer(f"Товар с ID {product_id} не найден.")
        return

    # Скачиваем фото из Telegram
    file_id = message.photo[-1].file_id
    file_path = f"{product_id}.jpg"
    full_path = os.path.join(PRODUCT_PHOTOS_DIR, file_path)
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, full_path)
        # Обновляем БД
        update_product(product_id, local_photo=full_path)
        await message.answer(f"Фото сохранено и привязано к товару #{product_id} «{html_escape(product['title'])}»")
    except Exception as e:
        logger.error(f"Ошибка сохранения фото товара #{product_id}: {e}")
        await message.answer(f"Ошибка сохранения фото: {e}")


# Хендлер без команды — админ просто шлёт фото, а бот определяет ID
@router.message(F.photo & ~F.caption)
async def product_photo_no_caption(message: Message):
    """Фото без подписи — подсказываем формат"""
    if not is_admin(message.from_user.id):
        return
    await message.answer("Чтобы привязать фото к товару, отправьте фото с ID товара в подписи.\nПример: фото с подписью «123»")


# ========================
# БЭКАП
# ========================

@router.message(text_match(BTN_BACKUP))
async def cmd_backup(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        backup_path = backup_db()
        size = os.path.getsize(backup_path)
        await message.answer(f"<b>Бэкап создан!</b>\n\n{html_escape(backup_path)}\n{size // 1024} KB", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"{e}")


# ========================
# БАН-ЛИСТ
# ========================

@router.message(text_match(BTN_BANLIST))
async def show_ban_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    banned = get_banned_users()
    if not banned:
        await message.answer("<b>Бан-лист пуст</b>\n\n/ban <user_id> <причина>\n/unban <user_id>", parse_mode="HTML")
        return
    text = "<b>Бан-лист</b>\n\n"
    for u in banned:
        text += f"<b>{u['user_id']}</b> ({html_escape(u['username'] or '?')})\n  Причина: {html_escape(u['reason'] or 'Не указана')}\n  {u['date']}\n\n"
    await message.answer(text, parse_mode="HTML")


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Использование: /ban <user_id> <причина>")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    reason = parts[2] if len(parts) > 2 else "Нарушение правил"
    ban_user(uid, reason=reason)
    await message.answer(f"Пользователь {uid} забанен.\nПричина: {reason}")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.split(maxsplit=1)[1])
    except (IndexError, ValueError):
        await message.answer("Использование: /unban <user_id>")
        return
    unban_user(uid)
    await message.answer(f"Пользователь {uid} разбанен.")


# ========================
# НАВИГАЦИЯ
# ========================

@router.callback_query(F.data.startswith("del_"))
async def delete_product_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    prod_id = int(callback.data.split("_")[1])
    delete_product(prod_id)
    await callback.answer("Товар удалён", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("edit_"))
async def edit_product_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    prod_id = int(callback.data.split("_")[1])
    product = get_product(prod_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await state.update_data(product_id=prod_id)
    await state.set_state(EditProductFSM.enter_title)
    await callback.message.answer(
        f"<b>Редактирование товара #{prod_id}</b>\n\n"
        f"Текущее название: {html_escape(product['title'])}\n"
        f"Введите новое название (или «-» чтобы оставить):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(EditProductFSM.enter_title)
async def edit_product_title(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    data = await state.get_data()
    prod_id = data["product_id"]
    product = get_product(prod_id)
    title = message.text.strip()
    if title == "-" or not title:
        title = product["title"]
    await state.update_data(new_title=title)
    await state.set_state(EditProductFSM.enter_desc)
    await message.answer(
        f"Текущее описание: {html_escape(product['desc'] or '—')}\n"
        f"Введите новое описание (или «-» чтобы оставить):",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )


@router.message(EditProductFSM.enter_desc)
async def edit_product_desc(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    data = await state.get_data()
    prod_id = data["product_id"]
    product = get_product(prod_id)
    desc = message.text.strip()
    if desc == "-" or not desc:
        desc = product["desc"]
    await state.update_data(new_desc=desc)
    await state.set_state(EditProductFSM.enter_price)
    await message.answer(
        f"Текущая цена: {product['price']} ₽\n"
        f"Введите новую цену (или «-» чтобы оставить):",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )


@router.message(EditProductFSM.enter_price)
async def edit_product_price(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    data = await state.get_data()
    prod_id = data["product_id"]
    product = get_product(prod_id)
    price_str = message.text.strip()
    if price_str == "-" or not price_str:
        price = product["price"]
    else:
        try:
            price = int(price_str)
        except ValueError:
            await message.answer("Цена должна быть числом. Попробуйте ещё раз:")
            return
    await state.update_data(new_price=price)
    stock = product.get("stock", -1)
    await state.set_state(EditProductFSM.enter_stock)
    await message.answer(
        f"Текущий запас: {str(stock) if stock >= 0 else 'не указан'}\n"
        f"Введите количество на складе (или «-» чтобы оставить):",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )


@router.message(EditProductFSM.enter_stock)
async def edit_product_stock(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu(user_id=message.from_user.id))
        return
    data = await state.get_data()
    prod_id = data["product_id"]
    product = get_product(prod_id)
    stock_str = message.text.strip()
    if stock_str == "-" or not stock_str:
        stock = product.get("stock", -1)
    else:
        try:
            stock = int(stock_str)
        except ValueError:
            await message.answer("Количество должно быть числом. Попробуйте ещё раз:")
            return
    update_product(prod_id, title=data["new_title"], desc=data["new_desc"], price=data["new_price"], stock=stock)
    await state.clear()
    await message.answer(
        f"✅ Товар #{prod_id} обновлён!\n\n"
        f"Название: {html_escape(data['new_title'])}\n"
        f"Описание: {html_escape(data['new_desc'])}\n"
        f"Цена: {data['new_price']} ₽\n"
        f"Запас: {str(stock) if stock >= 0 else 'не указан'}",
        reply_markup=main_menu(user_id=message.from_user.id), parse_mode="HTML"
    )


@router.message(Command("products"))
async def cmd_list_products(message: Message):
    if not is_admin(message.from_user.id):
        return
    products = get_products()
    if not products:
        await message.answer("Нет товаров.")
        return
    text = "<b>📦 Все товары</b>\n\n"
    for p in products[:20]:
        s = p.get("stock", -1)
        stock_str = f" ({s} шт.)" if s >= 0 else ""
        text += f"#{p['id']} {html_escape(p['title'])} — {p['price']}₽{stock_str}\n"
    await message.answer(text, parse_mode="HTML")


@router.message(Command("stock"))
async def cmd_stock(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) != 3:
        products = get_products()
        lines = []
        for p in products[:20]:
            s = p.get("stock", -1)
            if s >= 0:
                lines.append(f"#{p['id']} {html_escape(p['title'])} — {s} шт.")
            else:
                lines.append(f"#{p['id']} {html_escape(p['title'])} — не указан")
        await message.answer(
            "<b>📊 Запас товаров</b>\n\n" + "\n".join(lines) +
            "\n\n<i>Использование:</i> <code>/stock {id} {количество}</code>",
            parse_mode="HTML"
        )
        return
    try:
        prod_id = int(args[1])
        qty = int(args[2])
    except ValueError:
        await message.answer("ID и количество должны быть числами.")
        return
    product = get_product(prod_id)
    if not product:
        await message.answer(f"Товар #{prod_id} не найден.")
        return
    update_product(prod_id, stock=qty)
    await message.answer(f"✅ Запас товара #{prod_id} «{html_escape(product['title'])}»: {qty} шт.")


@router.message(text_match(BTN_BACK))
async def back_to_main(message: Message):
    await message.answer("Главное меню:", reply_markup=main_menu(user_id=message.from_user.id))
