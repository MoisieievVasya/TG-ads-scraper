import asyncio
import re
from datetime import date, datetime
from pathlib import Path

import imagehash
import requests
from PIL import Image
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

import shared_state
from database.models import Session, Business, AdCreative


# --- КОНФІГУРАЦІЯ СКРАПЕРА ---
MAIN_CONTENT_SELECTOR = '#mount_0_0_lg'
# URL-шаблон для бібліотеки реклами Facebook
ADS_URL_TEMPLATE = 'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&is_targeted_country=false&media_type=image_and_meme&search_type=page&view_all_page_id={}'

# Мапа для перетворення українських місяців на англійські
MONTH_MAP = {
    'січ': 'Jan', 'лют': 'Feb', 'бер': 'Mar',
    'квіт': 'Apr', 'кві': 'Apr',
    'трав': 'May',
    'черв': 'Jun', 'чер': 'Jun',
    'лип': 'Jul', 'серп': 'Aug', 'вер': 'Sep', "сер": 'Aug',
    'жовт': 'Oct',"жов": 'Oct', 'лис': 'Nov', 'груд': 'Dec', "гру": "Dec"
}


IMAGES_DIR = Path('images')
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def parse_start_date(text: str) -> date | None:
    """Витягує та перетворює дату запуску реклами з текстового рядка."""
    match = re.search(r'Початок показу:\s*(\d{1,2})\s+([а-яґєії]+)\s+(\d{4})', text, re.IGNORECASE)
    if not match:
        return None

    day, month_ukr, year = match.groups()
    month_ukr_lower = month_ukr.lower()
    month_eng = None

    for key, value in MONTH_MAP.items():
        if month_ukr_lower.startswith(key):
            month_eng = value
            break

    if not month_eng:
        print(f"  -> Помилка: Невідомий місяць '{month_ukr}'. Не знайдено відповідника в MONTH_MAP.")
        return None

    try:
        date_str = f'{day} {month_eng} {year}'
        return datetime.strptime(date_str, '%d %b %Y').date()
    except ValueError as e:
        print(f"  -> Помилка парсингу дати '{date_str}': {e}")
        return None


def download_image(ad_id: str, img_url: str) -> str | None:
    """Завантажує одне зображення та повертає локальний шлях."""
    local_path = IMAGES_DIR / f'{ad_id}.jpg'
    try:
        r = requests.get(img_url, timeout=15)
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            f.write(r.content)
        print(f"    - Збережено зображення: {local_path}")
        return str(local_path)
    except requests.exceptions.RequestException as req_err:
        print(f"    - Помилка завантаження зображення для {ad_id}: {req_err}")
        return None


async def fetch_ads_for_business(page, business: Business):
    """
    Витягує рекламні оголошення для конкретного бізнесу, реалізуючи всю фінальну логіку.
    """
    url = ADS_URL_TEMPLATE.format(business.fb_page_id)
    print(f"  -> Перехід до URL для бізнесу '{business.name}' (ID: {business.fb_page_id})")

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    except Exception as e:
        print(f"  -> Не вдалося завантажити URL: {e}")
        return

    try:
        print("  -> Шукаю спливаюче вікно cookie...")
        cookie_button = page.locator(
            '//button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "allow all")]'
            '| //button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "accept all")]'
            '| //button[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "дозволити")]'
        ).first
        await cookie_button.wait_for(timeout=7000)
        await cookie_button.click()
        print("  -> Спливаюче вікно cookie успішно закрито.")
        await page.wait_for_timeout(2000)
    except Exception:
        print("  -> Спливаюче вікно cookie не знайдено, продовжую...")

    print("  -> Прокручую сторінку для завантаження оголошень...")
    for _ in range(5):
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(2)

    try:
        print("  -> Очікую 5 секунд, щоб сторінка гарантовано завантажилася...")
        await page.wait_for_timeout(5000)
        print("  -> Отримую HTML-вміст сторінки...")
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        print(f"  -> Помилка під час фіксованого очікування або отримання контенту: {e}")
        screenshot_path = f"debug_screenshot_{business.fb_page_id}.png"
        await page.screenshot(path=screenshot_path)
        print(f"  -> Збережено скріншот для аналізу: {screenshot_path}.")
        return

    # 1. Збираємо картки для всіх унікальних ID оголошень
    ad_cards_map = {}
    id_elements = soup.find_all(string=re.compile(r'Ідентифікатор бібліотеки:'))

    for id_element in id_elements:
        ad_id_match = re.search(r'Ідентифікатор бібліотеки:\s*(\d+)', id_element.string)
        if not ad_id_match: continue
        ad_id = ad_id_match.group(1)

        if ad_id in ad_cards_map: continue

        ad_card = None
        for parent in id_element.find_parents('div'):
            if parent.find('hr'):
                ad_card = parent
                break
        if ad_card:
            ad_cards_map[ad_id] = ad_card

    print(f"  -> Знайдено {len(ad_cards_map)} унікальних оголошень для '{business.name}'.")
    if not ad_cards_map:
        return

    today = date.today()
    session = Session()
    try:
        scraped_ad_ids = set(ad_cards_map.keys())

        # 2. Обробляємо кожне унікальне оголошення
        for ad_id, ad_card in ad_cards_map.items():
            existing_ad = session.query(AdCreative).filter_by(fb_ad_id=ad_id).first()

            if existing_ad:
                # ОНОВЛЕННЯ ІСНУЮЧОГО
                existing_ad.last_seen = today
                existing_ad.is_active = True
                existing_ad.duration_days = (today - existing_ad.start_date).days + 1
                print(f"    - Оновлено оголошення: ID {ad_id}, днів: {existing_ad.duration_days}")
            else:
                # ДОДАВАННЯ НОВОГО
                start_date = parse_start_date(ad_card.get_text(separator=' '))
                if not start_date:
                    print(f"  -> Помилка: Не знайдено дату початку в оголошенні {ad_id}.")
                    continue

                # Логіка завантаження другого зображення
                all_img_tags = ad_card.find_all('img')
                img_url, local_path, image_hash_str = None, None, None

                if len(all_img_tags) > 1:
                    img_tag = all_img_tags[1]
                    src = img_tag.get('src')
                    if src:
                        img_url = src
                        local_path = download_image(ad_id, src)
                        # Розрахунок перцептивного хешу
                        if local_path:
                            try:
                                hash_value = imagehash.phash(Image.open(local_path))
                                image_hash_str = str(hash_value)
                            except Exception as e:
                                print(f"    - Помилка розрахунку хешу для {local_path}: {e}")
                else:
                    print(f"    - Попередження: Не знайдено другого зображення для нового оголошення {ad_id}.")

                # Витягнення кількості використання у інших рекламах
                similar_ads_count = 0
                card_text = ad_card.get_text()
                match = re.search(r'використовуються в\s+(\d+)\s+оголошеннях', card_text)
                if match:
                    similar_ads_count = int(match.group(1))

                new_ad = AdCreative(
                    fb_ad_id=ad_id,
                    business_id=business.id,
                    image_url=img_url,
                    local_path=local_path,
                    image_hash=image_hash_str,
                    similar_ads_count=similar_ads_count,
                    start_date=start_date,
                    last_seen=today,
                    is_active=True,
                    duration_days=(today - start_date).days + 1
                )
                session.add(new_ad)
                print(f"    - Додано нове оголошення: ID {ad_id}, схожих: {similar_ads_count}, днів: {new_ad.duration_days}.")

        # 3. Деактивація старих оголошень
        active_db_ads = session.query(AdCreative).filter_by(business_id=business.id, is_active=True).all()
        for ad in active_db_ads:
            if ad.fb_ad_id not in scraped_ad_ids:
                ad.is_active = False
                ad.end_date = today
                print(f"    - Деактивовано оголошення: ID {ad.fb_ad_id}.")

        session.commit()
        print(f"  -> Зміни для бізнесу '{business.name}' збережено.")
    except Exception as e:
        session.rollback()
        print(f"  -> КРИТИЧНА ПОМИЛКА обробки '{business.name}': {e}. Зміни відкочено.")
    finally:
        session.close()


async def scrape_all():
    """Головна функція, яка запускає скрапінг для всіх бізнесів з бази даних."""

    # Перевіряємо, чи не йде вже скрапінг
    if shared_state.is_scraping:
        print("🟡 Спроба запуску скрапінгу, але попередній процес ще активний. Пропускаємо.")
        return

    # Встановлюємо "замок"
    shared_state.is_scraping = True
    print("--- Процес скрапінгу розпочато, встановлено замок. ---")

    try:
        session = Session()
        businesses = session.query(Business).all()
        session.close()

        if not businesses:
            print("У базі даних немає бізнесів для скрапінгу.")
            return

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                for business in businesses:
                    print(f"Починаю скрапінг для бізнесу: '{business.name}'")
                    await fetch_ads_for_business(page, business)
                    print(f"Закінчено скрапінг для бізнесу: '{business.name}'\n")

            except Exception as e:
                print(f"Критична помилка під час роботи браузера: {e}")
            finally:
                if browser:
                    await browser.close()
                    print("Браузер Playwright закрито.")
    finally:
        # Щоб замок точно знявся
        shared_state.is_scraping = False
        print("--- Процес скрапінгу завершено, замок знято. ---")

# тестовий скрапінг
if __name__ == '__main__':
    asyncio.run(scrape_all())