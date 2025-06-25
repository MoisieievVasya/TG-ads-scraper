from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup


def business_filter_keyboard(businesses):
    buttons = [
        [InlineKeyboardButton(text=b.name, callback_data=f"filter_{b.id}")]
        for b in businesses
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard():
    """
    Створює і повертає клавіатуру головного меню.
    """
    # Створюємо кнопки
    report_button = KeyboardButton(text="📊 Звіт по унікальних") # Для команди /report
    report_all_button = KeyboardButton(text="🗂️ Звіт по всіх")      # Для команди /reportall
    scrape_button = KeyboardButton(text="⚙️ Запустити скрапінг")   # Для команди /scrape
    # long_ads_button = KeyboardButton(text="⏳ Довготривалі креативи") # Для команди /long

    # Створюємо клавіатуру, розміщуючи кнопки по дві в ряд
    main_menu_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [report_button, report_all_button],
            [scrape_button]
        ],
        resize_keyboard=True, # Робить кнопки меншими та зручнішими
        one_time_keyboard=False # Клавіатура не зникатиме після натискання
    )
    return main_menu_keyboard