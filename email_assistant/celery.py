"""Celery app configuration for email_assistant."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "email_assistant.settings")

app = Celery("email_assistant")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
