# main.py
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

# Импорты ваших модулей (убедитесь, что имена файлов правильные)
from database import init_db
from developer_scraper import scrape_developer_page   # ← если файл называется developer_scraper.py
# Если вы оставили gp_scraper.py — замените на: from gp_scraper import scrape_developer_page

from config import DEVELOPER_URLS, COUNTRIES, LANG, SCAN_INTERVAL_HOURS

logger.add("logs/scraper_{time:YYYY-MM-DD}.log", rotation="10 MB", level="INFO")

async def full_scan():
    """Одно полное сканирование всех издателей и стран"""
    init_db()
    semaphore = asyncio.Semaphore(5)  # Максимум 5 браузеров одновременно (комфортно для ПК)

    tasks = []
    for dev_id in DEVELOPER_URLS:
        for country in COUNTRIES:
            tasks.append(
                scrape_developer_page(developer_id=dev_id, 
                                      country=country, 
                                      lang=LANG, 
                                      semaphore=semaphore)
            )

    await asyncio.gather(*tasks, return_exceptions=True)
    logger.success("✅ Полное сканирование завершено!")

async def main():
    """Главная асинхронная функция"""
    logger.info(f"🚀 Мониторинг Google Play запущен! Сканирование каждые {SCAN_INTERVAL_HOURS} часов.")

    # Первое сканирование сразу при запуске
    await full_scan()

    # Настройка планировщика
    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")  # или "UTC"
    scheduler.add_job(
        full_scan, 
        trigger='interval', 
        hours=SCAN_INTERVAL_HOURS,
        id='developer_scan',
        replace_existing=True
    )
    scheduler.start()

    logger.info("⏰ Планировщик запущен. Нажмите Ctrl+C для остановки.")

    # Держим скрипт живым
    try:
        while True:
            await asyncio.sleep(3600)  # спим по часу, чтобы не нагружать CPU
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("🛑 Остановка мониторинга...")
        scheduler.shutdown()
        logger.info("✅ Скрипт остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Скрипт завершён пользователем.")