from celery import Celery
from celery.schedules import crontab
from utils.logging_config import setup_logging

# Создаём приложение Celery
celery_app = Celery(
    "lalafo_bot",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
    include=[
        "utils.tasks",
        "utils.tasks_single",
    ]
)

# Конфигурация
celery_app.conf.update(
    timezone="Asia/Bishkek",
    enable_utc=True,
)

# Планировщик (beat)
celery_app.conf.beat_schedule = {
    "check-ads-every-15-min": {
        "task": "utils.tasks.run_process_filters",
        "schedule": crontab(minute="*/15"),
    },
}

# Настройка логирования
setup_logging()

