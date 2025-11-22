from celery import Celery

celery_app = Celery("translator", broker="redis://redis:6379/0", backend="redis://redis:6379/1")
