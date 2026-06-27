"""
Рассылка подписчикам (админ-функция)
"""
import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import MailingFSM
from db import get_subscribers
from keyboards import mailing_actions, main_menu, cancel_kb
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id):
    return user_id in ADMIN_IDS


@router.message(F.text == "📬 Рассылка")
async def cmd_mailing(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(MailingFSM.enter_text)
    await message.answer(
        "📬 <b>Рассылка подписчикам</b>\n\n"
        "Напишите текст рассылки (поддерживается HTML):\n\n"
        "<code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "<code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
        "<code>&lt;a href='...'&gt;ссылка&lt;/a&gt;</code>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )


@router.message(MailingFSM.enter_text)
async def mailing_text(message: Message, state: FSMContext):
    if message.text == "✕ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu())
        return

    await state.update_data(text=message.text, html=message.html_text)
    await state.set_state(MailingFSM.add_photo)

    await message.answer(
        "📬 Текст сохранён.\n\n"
        "Теперь отправьте <b>фото</b> для рассылки (или отправьте «-» без фото):",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )


@router.message(MailingFSM.add_photo)
async def mailing_photo(message: Message, state: FSMContext):
    if message.text == "✕ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu())
        return

    photo = ""
    if message.photo:
        photo = message.photo[-1].file_id
    elif message.text and message.text.strip() == "-":
        photo = ""
    else:
        await message.answer("Отправьте фото или «-» чтобы пропустить.")
        return

    await state.update_data(photo=photo)
    data = await state.get_data()

    # Превью
    preview = f"📬 <b>Предпросмотр рассылки</b>\n\n{data['text']}\n\n"
    subscribers = get_subscribers()
    preview += f"👥 Получателей: <b>{len(subscribers)}</b>"

    await message.answer(
        preview,
        reply_markup=mailing_actions(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "mail_send")
async def mailing_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    subscribers = get_subscribers()
    text = data.get("text", "")
    html = data.get("html", text)
    photo = data.get("photo", "")

    await callback.message.edit_text(
        f"📬 Отправка рассылки {len(subscribers)} подписчикам..."
    )

    sent = 0
    failed = 0

    for sub in subscribers:
        try:
            if photo:
                await bot.send_photo(
                    chat_id=sub["user_id"],
                    photo=photo,
                    caption=html,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=sub["user_id"],
                    text=html,
                    parse_mode="HTML"
                )
            sent += 1
            await asyncio.sleep(0.05)  # flood control
        except Exception as e:
            failed += 1
            logger.warning(f"Mail send failed to {sub['user_id']}: {e}")

    await callback.message.edit_text(
        f"Рассылка завершена\n\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}\n"
        f"Всего подписчиков: {len(subscribers)}",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "mail_edit")
async def mailing_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MailingFSM.enter_text)
    await callback.message.edit_text(
        "Введите новый текст рассылки:",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "mail_cancel")
async def mailing_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.")
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer()
