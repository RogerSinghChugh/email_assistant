"""Sync (no Celery) management command for validating the LLM round-trip end-to-end.

Usage::

    python manage.py refresh_summary <thread_id>
"""

from django.core.management.base import BaseCommand, CommandError

from apps.summaries.services.summarizer import SummaryService


class Command(BaseCommand):
    help = "Synchronously regenerate the summary for a thread (debug/validation tool)."

    def add_arguments(self, parser):
        parser.add_argument(
            "thread_id", type=str, help="UUID of the thread to summarize."
        )

    def handle(self, *args, thread_id, **opts):
        try:
            result = SummaryService().refresh(thread_id)
        except Exception as exc:
            raise CommandError(f"Refresh failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(f"Summary refreshed for thread {thread_id}")
        )
        self.stdout.write(f"  emails_analyzed: {result.emails_analyzed}")
        self.stdout.write(f"  actors: {[a.name for a in result.payload.actors]}")
        self.stdout.write(f"  conclusions: {len(result.payload.conclusions)} item(s)")
        self.stdout.write(f"  action_items: {len(result.payload.action_items)} item(s)")
