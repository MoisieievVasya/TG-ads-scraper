import logging

logger = logging.getLogger(__name__)
from collections import defaultdict
from datetime import date, timedelta

import imagehash
from aiogram import types, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, InputMediaPhoto
from sqlalchemy.orm import joinedload

import shared_state
from database.models import Session, Business, AdCreative
from facebook.scraper import scrape_all
from bot.keyboards import get_main_menu_keyboard
from bot.states import ReportState, ReportAllState

router = Router()


@router.message(Command("add_business"))
async def add_business_command(message: types.Message, command: CommandObject):
    """
    Додає новий бізнес для моніторингу в базу даних.
    Формат: /add_business <ID сторінки> <Назва бізнесу>
    """
    if not command.args:
        await message.answer(
            "❌ Будь ласка, вкажіть ID сторінки та назву бізнесу.\n"
            "Приклад: `/add_business 1234567890 Nike`"
        )
        return

    # Поділ id і назви
    args = command.args.split(maxsplit=1)
    if len(args) != 2:
        await message.answer(
            "❌ Неправильний формат команди.\n"
            "Використовуйте: `/add_business <ID сторінки> <Назва бізнесу>`"
        )
        return

    fb_page_id, business_name = args

    session = Session()
    try:
        # тест чи є такий бізнес
        existing_business = session.query(Business).filter_by(fb_page_id=fb_page_id).first()
        if existing_business:
            await message.answer(f"⚠️ Бізнес '{existing_business.name}' з ID `{fb_page_id}` вже існує в базі.")
            return

        # коміт бізнесу
        new_business = Business(name=business_name, fb_page_id=fb_page_id)
        session.add(new_business)
        session.commit()

        await message.answer(f"✅ Бізнес '{business_name}' з ID `{fb_page_id}` успішно додано до моніторингу!")
        logger.info(f"Додано новий бізнес: {business_name} ({fb_page_id})")

    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Сталася помилка при додаванні в базу даних: {e}")
        logger.error(f"Помилка додавання бізнесу: {e}")
    finally:
        session.close()


@router.message(Command("delete_business"))
async def delete_business_command(message: types.Message, command: CommandObject):
    """
    Видаляє бізнес з бази даних за його ID.
    Формат: /delete_business <ID>
    """
    if not command.args or not command.args.strip().isdigit():
        await message.answer("❌ Будь ласка, вкажіть ID бізнесу для видалення.\nПриклад: /delete_business 2")
        return

    business_id = int(command.args.strip())
    session = Session()
    try:
        business = session.query(Business).filter_by(fb_page_id=str(business_id)).first()
        if not business:
            await message.answer(f"⚠️ Бізнес з ID `{business_id}` не знайдено.")
            return

        session.delete(business)
        session.commit()
        await message.answer(f"✅ Бізнес '{business.name}' (ID: {business_id}) успішно видалено.")
        logger.info(f"Видалено бізнес: {business.name} (ID: {business_id})")
    except Exception as e:
        session.rollback()
        await message.answer(f"❌ Помилка при видаленні бізнесу: {e}")
        logger.error(f"Помилка видалення бізнесу: {e}")
    finally:
        session.close()

@router.message(Command('start'))
async def start_handler(msg: types.Message):
    """
    Старт боту
    """
    keyboard = get_main_menu_keyboard()
    await msg.answer(
        '👋 Привіт! Оберіть дію за допомогою кнопок меню:',
        reply_markup=keyboard
    )


@router.message(Command('businesses'))
async def list_businesses(msg: types.Message):
    session = Session()
    businesses = session.query(Business).all()
    text = '\n'.join([f"{b.id}. {b.name}" for b in businesses])
    await msg.answer(f"📊 Моніторяться такі бізнеси:\n{text}")
    session.close()

# --- ТРЕБА ФІКСАНУТИ ---
# @router.message(F.text.in_({"⏳ Довготривалі креативи", "/long"}))
# async def long_ads(msg: types.Message):
#     """
#     Показує унікальні креативи, що активні 10+ днів,
#     з урахуванням схожості зображень.
#     """
#     await msg.answer("⏳ Шукаю довготривалі унікальні креативи...")
#
#     session = Session()
#     ads = session.query(AdCreative).options(joinedload(AdCreative.business)).filter(
#         AdCreative.duration_days >= 10,
#         AdCreative.is_active == True
#     ).order_by(AdCreative.start_date.desc()).all()
#     session.close()
#
#     if not ads:
#         await msg.answer("📊 Немає активних креативів, що працюють 10 або більше днів.")
#         return
#
#     HAMMING_DISTANCE_THRESHOLD = 14 #по тестам 14 найкраще відсіює схожі
#     unique_ads = []
#     processed_hashes = []
#
#     for ad in ads:
#         if not ad.image_hash or not ad.local_path:
#             continue
#         try:
#             current_hash = imagehash.hex_to_hash(ad.image_hash)
#             is_duplicate = False
#             for existing_hash_str in processed_hashes:
#                 existing_hash = imagehash.hex_to_hash(existing_hash_str)
#                 if current_hash - existing_hash <= HAMMING_DISTANCE_THRESHOLD:
#                     is_duplicate = True
#                     break
#             if not is_duplicate:
#                 unique_ads.append(ad)
#                 processed_hashes.append(ad.image_hash)
#         except Exception as e:
#             print(f"Помилка порівняння хешу для /long ad_id {ad.id}: {e}")
#
#     if not unique_ads:
#         await msg.answer("📊 Після фільтрації дублікатів не знайдено довготривалих креативів.")
#         return
#
#     await msg.answer(f"Знайдено {len(unique_ads)} унікальних креативів, що працюють 10+ днів:")
#     for ad in unique_ads:
#         caption = (f"<b>{ad.business.name}</b>\n"
#                    f"Тривалість: {ad.duration_days} дн.\n"
#                    f"Схожих варіацій (за даними FB): {ad.similar_ads_count}")
#         try:
#             await msg.answer_photo(FSInputFile(ad.local_path), caption=caption, parse_mode="HTML")
#         except Exception as e:
#             print(f"Помилка відправки фото для /long: {e}")
#             await msg.answer(f"Не вдалося завантажити фото для ID: {ad.fb_ad_id}")


@router.message(F.text.in_({"📊 Звіт по унікальних", "/report"}))
async def report_start(message: types.Message, state: FSMContext):
    """Починає процес створення звіту, питає про період."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Сьогодні", callback_data="report_period_today")],
        [InlineKeyboardButton(text="🔵 Цей тиждень", callback_data="report_period_week")],
        [InlineKeyboardButton(text="🟣 Цей місяць", callback_data="report_period_month")],
        [InlineKeyboardButton(text="⚫️ За весь час", callback_data="report_period_all")],
    ])
    await message.answer("🗓️ Оберіть період для звіту:", reply_markup=keyboard)
    await state.set_state(ReportState.waiting_for_period)


@router.callback_query(ReportState.waiting_for_period)
async def period_chosen(call: types.CallbackQuery, state: FSMContext):
    """Обробляє вибір періоду, зберігає його і питає про бізнес."""
    await call.answer()
    period = call.data.split('_')[-1]
    await state.update_data(period=period)

    session = Session()
    businesses = session.query(Business).all()
    session.close()

    buttons = [[InlineKeyboardButton(text=b.name, callback_data=f"report_biz_{b.id}")] for b in businesses]
    buttons.append([InlineKeyboardButton(text="📈 Всі бізнеси", callback_data="report_biz_all")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.edit_text("🏢 Тепер оберіть бізнес:", reply_markup=keyboard)
    await state.set_state(ReportState.waiting_for_business)


@router.callback_query(ReportState.waiting_for_business)
async def business_chosen(call: types.CallbackQuery, state: FSMContext):
    """
    Фінальний крок. Формує звіт, розраховуючи кількість
    схожих креативів у вибраному періоді.
    """
    await call.answer()
    await call.message.edit_text("⏳ Готую звіт, аналізую та групую креативи...")

    user_data = await state.get_data()
    period = user_data['period']
    business_id_str = call.data.split('_')[-1]

    # --- 1. Отримуємо кандидатів з БД ---
    session = Session()
    query = session.query(AdCreative).options(joinedload(AdCreative.business))

    if period != 'all':
        query = query.filter(AdCreative.is_active == True)

    today = date.today()
    if period == 'today':
        query = query.filter(AdCreative.start_date == today)
        period_str = f"за {today.strftime('%d.%m.%Y')}"
    elif period == 'week':
        start_date = today - timedelta(days=7)
        query = query.filter(AdCreative.start_date >= start_date)
        period_str = f"з {start_date.strftime('%d.%m')} по {today.strftime('%d.%m')}"
    elif period == 'month':
        start_date = today - timedelta(days=30)
        query = query.filter(AdCreative.start_date >= start_date)
        period_str = f"за останні 30 днів"
    else:
        period_str = "за весь час"

    business_name = "Всі бізнеси"
    if business_id_str != 'all':
        business_id = int(business_id_str)
        query = query.filter(AdCreative.business_id == business_id)
        business = session.query(Business).filter_by(id=business_id).first()
        if business:
            business_name = business.name

    ads = query.order_by(AdCreative.start_date.desc()).all()
    session.close()

    if not ads:
        await call.message.edit_text("🤷‍♂️ За обраними критеріями нічого не знайдено.")
        await state.clear()
        return

    # --- 2. ДИНАМІЧНЕ ГРУПУВАННЯ ЗА ХЕШЕМ ---
    HAMMING_DISTANCE_THRESHOLD = 14
    hash_groups = []

    for ad in ads:
        if not ad.image_hash or not ad.local_path:
            continue

        try:
            current_hash = imagehash.hex_to_hash(ad.image_hash)
            found_group = False
            for group in hash_groups:
                representative_hash = imagehash.hex_to_hash(group[0].image_hash)
                if current_hash - representative_hash <= HAMMING_DISTANCE_THRESHOLD:
                    group.append(ad)
                    found_group = True
                    break
            if not found_group:
                hash_groups.append([ad])
        except Exception as e:
            logger.error(f"Помилка обробки хешу для ad_id {ad.id}: {e}")

    if not hash_groups:
        await call.message.edit_text("🤷‍♂️ Не вдалося знайти креативи з зображеннями для аналізу.")
        await state.clear()
        return

    # --- 3. Категоризуємо групи за їхнім розміром ---
    top_performers = []  # 5+ копій
    mid_performers = []  # 2-4 копії
    single_creatives = []  # 1 копія

    for group in hash_groups:
        group_size = len(group)
        representative_ad = group[0]
        item_to_categorize = (representative_ad, group_size)

        if group_size >= 5:
            top_performers.append(item_to_categorize)
        elif 2 <= group_size <= 4:
            mid_performers.append(item_to_categorize)
        else:
            single_creatives.append(item_to_categorize)

    # --- 4. Надсилаємо звіт ---
    await call.message.delete()
    await call.message.answer(f"<b>Звіт для: {business_name}</b> ({period_str})", parse_mode="HTML")

    await send_ads_category(
        call.message, top_performers,
        f"<b>🔥 Креативи-лідери ({len(top_performers)} унікальних, 5+ варіацій)</b>"
    )
    await send_ads_category(
        call.message, mid_performers,
        f"<b>💪 Стабільні креативи ({len(mid_performers)} унікальних, 2-4 варіації)</b>"
    )
    await send_ads_category(
        call.message, single_creatives,
        f"<b>🤔 Одиничні креативи/тести ({len(single_creatives)} унікальних)</b>"
    )

    await call.message.answer("✅ Звіт готовий!")
    await state.clear()

@router.message(F.text.in_({"⚙️ Запустити скрапінг", "/scrape"}))
async def manual_scrape_command(message: types.Message):
    """
    Обробник для ручного запуску процесу скрапінгу з перевіркою стану.
    """
    # Перевіряємо, чи не йде вже скрапінг
    if shared_state.is_scraping:
        await message.answer("⏳ Процес скрапінгу вже запущено. Будь ласка, зачекайте його завершення.")
        return

    await message.answer("⚙️ Починаю процес скрапінгу... Це може зайняти кілька хвилин.")

    try:
        await scrape_all()
        await message.answer("✅ Скрапінг успішно завершено!")
    except Exception as e:
        logger.error(f"Помилка під час ручного скрапінгу: {e}")
        await message.answer(f"❌ Під час скрапінгу сталася помилка.\nДеталі: {e}")


@router.message(F.text.in_({"🗂️ Звіт по всіх", "/reportall"}))
async def report_all_start(message: types.Message, state: FSMContext):
    """Починає процес створення повного звіту, питає про період."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Сьогодні", callback_data="reportall_period_today")],
        [InlineKeyboardButton(text="🔵 Цей тиждень", callback_data="reportall_period_week")],
        [InlineKeyboardButton(text="🟣 Цей місяць", callback_data="reportall_period_month")],
        [InlineKeyboardButton(text="⚫️ За весь час", callback_data="reportall_period_all")],
    ])
    await message.answer("🗓️ Оберіть період для **повного** звіту (з усіма дублікатами):", reply_markup=keyboard)
    # Встановлюємо новий стан
    await state.set_state(ReportAllState.waiting_for_period)


@router.callback_query(ReportAllState.waiting_for_period)
async def period_chosen_all(call: types.CallbackQuery, state: FSMContext):
    """Обробляє вибір періоду для повного звіту."""
    await call.answer()
    period = call.data.split('_')[-1]
    await state.update_data(period=period)

    session = Session()
    businesses = session.query(Business).all()
    session.close()

    buttons = [[InlineKeyboardButton(text=b.name, callback_data=f"reportall_biz_{b.id}")] for b in businesses]
    buttons.append([InlineKeyboardButton(text="📈 Всі бізнеси", callback_data="reportall_biz_all")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.edit_text("🏢 Тепер оберіть бізнес:", reply_markup=keyboard)
    await state.set_state(ReportAllState.waiting_for_business)


@router.callback_query(ReportAllState.waiting_for_business)
async def business_chosen_all(call: types.CallbackQuery, state: FSMContext):
    """Фінальний крок. Формує і надсилає повний звіт БЕЗ фільтрації по хешу."""

    await call.answer() # для уникнення таймауту додано, але всеодно прилітаж помилка про флуд

    await call.message.edit_text("⏳ Готую **повний** звіт...")

    user_data = await state.get_data()
    period = user_data['period']
    business_id = call.data.split('_')[-1]

    session = Session()
    query = session.query(AdCreative).options(joinedload(AdCreative.business))

    if period != 'all':
        query = query.filter(AdCreative.is_active == True)

    today = date.today()
    if period == 'today':
        start_date = today
        query = query.filter(AdCreative.start_date == start_date)
        period_str = f"за {today.strftime('%d.%m.%Y')}"
    elif period == 'week':
        start_date = today - timedelta(days=7)
        query = query.filter(AdCreative.start_date >= start_date)
        period_str = f"з {start_date.strftime('%d.%m')} по {today.strftime('%d.%m')}"
    elif period == 'month':
        start_date = today - timedelta(days=30)
        query = query.filter(AdCreative.start_date >= start_date)
        period_str = f"за останні 30 днів"
    else:
        period_str = "за весь час"

    if business_id != 'all':
        query = query.filter(AdCreative.business_id == int(business_id))

    ads = query.order_by(AdCreative.business_id, AdCreative.start_date.desc()).all()
    session.close()

    if not ads:
        await call.message.edit_text("🤷‍♂️ За обраними критеріями нічого не знайдено.")
        await state.clear()
        return

    ads_by_business = defaultdict(list)
    for ad in ads:
        ads_by_business[ad.business].append(ad)

    await call.message.delete()

    for business, business_ads in ads_by_business.items():
        header_text = (f"<b>{business.name}</b>\n"
                       f"Всі креативи {period_str} (знайдено: {len(business_ads)}):")
        await call.message.answer(header_text, parse_mode="HTML")

        media_group = []
        for ad in business_ads:
            if ad.local_path:
                try:
                    media_group.append(InputMediaPhoto(media=FSInputFile(ad.local_path)))
                    if len(media_group) == 10:
                        await call.message.answer_media_group(media_group)
                        media_group = []
                except Exception as e:
                    logger.error(f"Помилка при додаванні фото в групу: {e}")

        if media_group:
            await call.message.answer_media_group(media_group)

    await call.message.answer("✅ Повний звіт готовий!")
    await state.clear()


async def send_ads_category(message: types.Message, ads_with_counts: list, header: str):
    """
    Надсилає заголовок і фото для заданої категорії оголошень.
    Приймає список кортежів (оголошення, кількість схожих).
    """
    if not ads_with_counts:
        return

    sorted_ads = sorted(ads_with_counts, key=lambda item: item[1], reverse=True)

    await message.answer(header, parse_mode="HTML")
    for ad, count in sorted_ads:
        if ad.local_path:
            caption = (f"Знайдено схожих у цьому звіті: <b>{count}</b>\n"
                       f"Тривалість: {ad.duration_days} дн.")
            try:
                await message.answer_photo(FSInputFile(ad.local_path), caption=caption, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Помилка відправки фото {ad.id}: {e}")