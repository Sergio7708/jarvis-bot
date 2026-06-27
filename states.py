"""
FSM-состояния для бота @Jarvisvetogorbot
"""
from aiogram.fsm.state import State, StatesGroup


class OrderFSM(StatesGroup):
    """Пошаговый заказ модели (новая версия — с корзиной)"""
    choose_product = State()      # выбор товара
    enter_material = State()      # выбор материала
    enter_color = State()         # выбор цвета
    enter_quantity = State()      # количество
    enter_contact = State()       # контакт (телефон/username)
    enter_comment = State()       # комментарий
    confirm = State()             # подтверждение


class CartFSM(StatesGroup):
    """Управление корзиной"""
    add_more = State()            # добавить ещё товар?
    checkout = State()            # оформление


class AddProductFSM(StatesGroup):
    """Добавление товара админом"""
    choose_category = State()
    enter_title = State()
    enter_desc = State()
    enter_price = State()
    upload_photo = State()
    confirm = State()


class EditProductFSM(StatesGroup):
    """Редактирование товара админом"""
    choose_product = State()
    enter_title = State()
    enter_desc = State()
    enter_price = State()
    enter_stock = State()
    confirm = State()


class AddCategoryFSM(StatesGroup):
    """Добавление категории админом"""
    enter_name = State()
    enter_emoji = State()
    enter_desc = State()


class EditCategoryFSM(StatesGroup):
    """Редактирование категории"""
    choose_category = State()
    choose_field = State()
    enter_value = State()


class MailingFSM(StatesGroup):
    """Рассылка подписчикам"""
    enter_text = State()
    add_photo = State()
    confirm = State()


class PhotoReportFSM(StatesGroup):
    """Фотоотчёт по заказу"""
    enter_caption = State()
    confirm = State()


class ReviewFSM(StatesGroup):
    """Отзыв на товар"""
    choose_product = State()
    enter_rating = State()
    enter_text = State()
    confirm = State()


class PaymentFSM(StatesGroup):
    """Оплата заказа"""
    choose_method = State()
    confirm = State()
