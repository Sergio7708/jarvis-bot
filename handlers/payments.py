"""
Оплата заказов — ЮKassa + альтернативные методы
"""
import asyncio
import logging
from aiogram import Router, types, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import PaymentFSM
from db import get_order, create_payment, update_payment_status, get_payment
from keyboards import payment_methods, main_menu, cancel_kb
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY

logger = logging.getLogger(__name__)
router = Router()


async def create_yookassa_payment(amount, order_id, description):
    """Создать платёж в ЮKassa"""
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        return None, "ЮKassa не настроена. Обратитесь к администратору."

    try:
        import json
        import base64

        auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()

        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/Jarvisvetogorbot"
            },
            "capture": True,
            "description": description,
            "metadata": {
                "order_id": str(order_id)
            }
        }

        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {auth}",
                    "Idempotence-Key": f"order_{order_id}_{asyncio.get_event_loop().time()}"
                },
                timeout=15
            )

        if resp.status_code == 200:
            data = resp.json()
            return data, None
        else:
            logger.error(f"YooKassa error {resp.status_code}: {resp.text}")
            return None, f"Ошибка платежа: {resp.status_code}"

    except Exception as e:
        logger.error(f"YooKassa exception: {e}")
        return None, f"Ошибка подключения к платёжному шлюзу: {e}"


@router.message(F.text == "💳 Оплатить")
async def cmd_payment(message: Message, state: FSMContext):
    await state.set_state(PaymentFSM.choose_method)
    await message.answer(
        "💳 <b>Оплата заказа</b>\n\nВыберите способ оплаты:",
        reply_markup=payment_methods(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("pay_order_"))
async def pay_order(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await state.update_data(order_id=order_id, amount=order.get("total_price", 0))
    await state.set_state(PaymentFSM.choose_method)

    await callback.message.edit_text(
        f"💳 <b>Оплата заказа #{order_id}</b>\n\n"
        f"Сумма: {order.get('total_price', 0)}₽\n\n"
        "Выберите способ оплаты:",
        reply_markup=payment_methods(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(PaymentFSM.choose_method, F.data == "pay_yookassa")
async def pay_yookassa(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    amount = data.get("amount", 0)

    if amount <= 0:
        await callback.message.edit_text(
            "Сумма заказа не определена. Уточните у администратора.",
            reply_markup=main_menu()
        )
        await state.clear()
        return

    await callback.message.edit_text("Создание платежа...")

    payment_data, error = await create_yookassa_payment(
        amount, order_id, f"Заказ #{order_id} — 3Д Моделист Конструктор"
    )

    if error:
        await callback.message.edit_text(
            f"Ошибка: {error}\n\n"
            f"Попробуйте другой способ оплаты или обратитесь к администратору.",
            reply_markup=payment_methods()
        )
        return

    payment_id = payment_data.get("id", "")
    confirmation_url = payment_data.get("confirmation", {}).get("confirmation_url", "")

    # Сохраняем в БД
    create_payment(
        order_id=order_id,
        user_id=callback.from_user.id,
        amount=amount,
        confirmation_url=confirmation_url
    )

    text = (
        f"💳 <b>Оплата заказа #{order_id}</b>\n\n"
        f"Сумма: {amount}₽\n"
        f"Платёж создан!\n\n"
        f"👇 Нажмите кнопку ниже, чтобы перейти к оплате:"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
        [InlineKeyboardButton(text="Я оплатил", callback_data=f"pay_check_{payment_id}")],
    ])

    try:
        await callback.message.edit_text(text, reply_markup=pay_kb, parse_mode="HTML",
                                         disable_web_page_preview=True)
    except Exception:
        await callback.message.answer(text, reply_markup=pay_kb, parse_mode="HTML",
                                      disable_web_page_preview=True)

    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("pay_check_"))
async def check_payment(callback: CallbackQuery):
    payment_id = callback.data.replace("pay_check_", "")

    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        await callback.answer("Автопроверка недоступна", show_alert=True)
        return

    try:
        import base64
        import httpx

        auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.yookassa.ru/v3/payments/{payment_id}",
                headers={"Authorization": f"Basic {auth}"},
                timeout=10
            )

        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")

            if status == "succeeded":
                await callback.message.edit_text(
                    f"<b>Оплата подтверждена!</b>\n\n"
                    f"Спасибо! Ваш заказ принят в обработку.",
                    parse_mode="HTML"
                )
                await callback.answer("Оплата прошла успешно!")
            elif status == "pending":
                await callback.answer("⏳ Платёж ещё обрабатывается...", show_alert=True)
            elif status == "canceled":
                await callback.answer("Платёж отменён", show_alert=True)
            else:
                await callback.answer(f"Статус: {status}", show_alert=True)
        else:
            await callback.answer("Не удалось проверить статус", show_alert=True)

    except Exception as e:
        logger.error(f"Payment check error: {e}")
        await callback.answer("Ошибка проверки", show_alert=True)


@router.callback_query(PaymentFSM.choose_method, F.data == "pay_card")
async def pay_card(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    amount = data.get("amount", 0)

    await callback.message.edit_text(
        f"💳 <b>Перевод на карту</b>\n\n"
        f"Сумма: {amount}₽\n\n"
        f"Реквизиты для перевода:\n"
        f"💳 <code>2200 7000 1234 5678</code>\n"
        f"👤 Получатель: Сергей И.\n"
        f"🏦 Сбербанк / Т-Банк\n\n"
        f"После перевода отправьте чёт в чат — мы подтвердим оплату.\n\n"
        f"Заказ #{order_id}",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(PaymentFSM.choose_method, F.data == "pay_cash")
async def pay_cash(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")

    await callback.message.edit_text(
        f"💵 <b>Оплата наличными</b>\n\n"
        f"Вы выбрали оплату наличными при получении.\n\n"
        f"Доступно при самовывозе или личной встрече.\n"
        f"Администратор свяжется с вами для уточнения.\n\n"
        f"Заказ #{order_id}",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()
