# test_celery.py
import time
import os
from dotenv import load_dotenv

# Подгрузим .env (важно, чтобы в нем были DATABASE_URL, BOT_TOKEN и т.д.)
load_dotenv()

from utils.tasks import run_process_filters
from utils.tasks_single import run_single_filter

def test_all_filters():
    print("Отправляем таску run_process_filters...")
    result = run_process_filters.delay()
    while not result.ready():
        print("Статус:", result.status)
        time.sleep(1)
    print("Итоговый статус:", result.status)
    print("Результат:", result.get())

def test_single_filter(filter_id=1):
    print(f"Отправляем таску run_single_filter (id={filter_id})...")
    result = run_single_filter.delay(filter_id=filter_id)
    while not result.ready():
        print("Статус:", result.status)
        time.sleep(1)
    print("Итоговый статус:", result.status)
    print("Результат:", result.get())

if __name__ == "__main__":
    # тест обработки всех фильтров
    test_all_filters()

    # тест обработки одного фильтра
    # поменяй ID на существующий в БД
    test_single_filter(filter_id=1)

