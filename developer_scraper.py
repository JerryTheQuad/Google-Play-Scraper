# scraper.py
import asyncio
from playwright.async_api import async_playwright
from loguru import logger
from database import get_known_apps, save_new_app
from notifier import send_notification

BAD_TITLE_MARKERS = {
    "покупки в приложении",
    "in-app purchases",
    "contains ads",
    "реклама",
}


def _is_bad_title(value: str) -> bool:
    normalized = " ".join(value.lower().split())
    return not normalized or normalized in BAD_TITLE_MARKERS


async def _extract_app_title(link):
    """
    Извлекает название приложения из карточки.
    В Google Play часто попадается служебный текст (например, "Покупки в приложении"),
    поэтому фильтруем такие значения и ищем более надёжные источники.
    """
    # 1) Самые надёжные варианты атрибутов/тегов
    for candidate_locator in [
        link.locator("img[alt]").first,
        link.locator("[aria-label]").first,
        link.locator("[title]").first,
    ]:
        if await candidate_locator.count() == 0:
            continue

        for attr in ("alt", "aria-label", "title"):
            value = await candidate_locator.get_attribute(attr)
            if value and not _is_bad_title(value.strip()):
                return value.strip()

    # 2) Заголовки и текстовые узлы карточки
    text_candidates = await link.locator(
        "span, div, h2, h3, [role='heading']"
    ).all_inner_texts()

    for value in text_candidates:
        cleaned = value.strip()
        if len(cleaned) >= 2 and not _is_bad_title(cleaned):
            return cleaned

    # 3) Fallback: любой текст карточки, но с фильтрацией служебных фраз
    card = link.locator("xpath=ancestor::div[contains(@class, 'VfPpkd') or contains(@class, 'Si6A0c') or contains(@class, 'card') or contains(@class, 'item')]").first
    if await card.count() > 0:
        all_text = await card.inner_text()
        lines = [line.strip() for line in all_text.split("\n") if line.strip()]
        for line in lines:
            if len(line) >= 2 and not _is_bad_title(line):
                return line

    return "Без названия"


async def scrape_developer_page(developer_id: str, country: str, lang: str, semaphore: asyncio.Semaphore):
    async with semaphore:
        developer_id = developer_id.strip().replace(" ", "+")
        
        urls_to_try = [
            f"{developer_id}&hl={lang}&gl={country}"
        ]

        found_apps = []
        success = False

        for url in urls_to_try:
            logger.info(f"Попытка сканирования: {developer_id} | {country} → {url}")
            
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.set_extra_http_headers({
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
                    })

                    await page.goto(url, wait_until="networkidle", timeout=60000)

                    # Проверка на 404
                    page_title = await page.title()
                    if "not found" in page_title.lower() or "страница не найдена" in (await page.content()).lower():
                        await browser.close()
                        continue

                    # Улучшенный скролл (больше попыток + пауза)
                    for _ in range(15):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(3)

                    # === УЛУЧШЕННЫЙ ПАРСИНГ НАЗВАНИЙ ===
                    # Основной локатор: все ссылки на детали приложений
                    app_links = await page.locator('a[href*="/store/apps/details?id="]').all()

                    for link in app_links:
                        href = await link.get_attribute("href")
                        if not href or "id=" not in href:
                            continue
                        
                        app_id = href.split("id=")[-1].split("&")[0].split("?")[0]
                        if not app_id:
                            continue

                        title = await _extract_app_title(link)

                        found_apps.append({"app_id": app_id, "title": title})

                    await browser.close()
                    success = True
                    logger.info(f"Успешно загружено {len(found_apps)} приложений с {url}")
                    break

            except Exception as e:
                logger.warning(f"Ошибка при попытке {url}: {e}")
                continue

        if not success:
            logger.error(f"Не удалось загрузить страницу издателя {developer_id}")
            return

        # === ДЕДУПЛИКАЦИЯ: одна игра — один раз ===
        # Используем set для уникальных app_id (самый надёжный способ)
        unique_apps = {}
        for app in found_apps:
            if app["app_id"] not in unique_apps:
                unique_apps[app["app_id"]] = app

        deduplicated_apps = sorted(unique_apps.values(), key=lambda app: app["app_id"])

        # Сравнение с БД
        known = get_known_apps(developer_id, country)
        new_apps = [app for app in deduplicated_apps if app["app_id"] not in known]

        if new_apps:
            logger.success(f"✅ НАЙДЕНО НОВЫХ приложений у {developer_id} ({country}): {len(new_apps)} (всего уникальных: {len(deduplicated_apps)})")
            notified_ids = set()
            for app in new_apps:
                if app["app_id"] in notified_ids:
                    continue

                save_new_app(developer_id, country, app["app_id"], app["title"])
                send_notification(
                    f"🆕 **Новая игра от издателя**\n"
                    f"Издатель: {developer_id}\n"
                    f"Страна: {country.upper()}\n"
                    f"Название: **{app['title']}**\n"
                    f"App ID: `{app['app_id']}`\n"
                    f"[Открыть →](https://play.google.com/store/apps/details?id={app['app_id']})"
                )
                notified_ids.add(app["app_id"])
        else:
            logger.info(f"Новых приложений не найдено у {developer_id} ({country}). Всего уникальных приложений: {len(deduplicated_apps)}")
