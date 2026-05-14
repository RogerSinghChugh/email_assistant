from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        from apps.core.logging import ensure_log_dir, register_celery_signal_handlers
        from apps.core.telemetry import setup_telemetry

        ensure_log_dir()
        register_celery_signal_handlers()
        setup_telemetry()
