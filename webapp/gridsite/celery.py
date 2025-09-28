import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gridsite.settings')

app = Celery('gridsite')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
