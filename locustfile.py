"""Locust load test for the Email Context backend.

Four user classes — pass class names as positional args to pick a scenario
(omit for the weighted mix of all classes):

    # Default: realistic read-heavy mix (all classes spawn, weighted)
    locust -f locustfile.py --host http://localhost:8000

    # Read-only stress (cache + DB hot path)
    locust -f locustfile.py --host http://localhost:8000 ReaderUser

    # Refresh fan-in proof — N users hammer ONE thread
    locust -f locustfile.py --host http://localhost:8000 DedupHammerUser

    # Admin/superuser report endpoints
    locust -f locustfile.py --host http://localhost:8000 \\
        AdminReportUser SuperReportUser

    # Headless run with a ramp + duration
    locust -f locustfile.py --host http://localhost:8000 \\
        --headless -u 50 -r 5 -t 60s ReaderUser

The seed command must have been run so the predefined credentials exist.
"""

from __future__ import annotations

import random

from locust import HttpUser, between, constant, task

PASSWORD = "Passw0rd!"

# Mixed pool — any seeded firm member. Used by the realistic-mix Reader.
FIRM_USERS = [
    f"firm{f}_member{m}@example.com" for f in (1, 2, 3, 4) for m in (1, 2, 3, 4, 5)
]
FIRM_ADMINS = [f"firm{f}_admin0@example.com" for f in (1, 2, 3, 4)]
SUPERUSER = "superadmin@example.com"

# Restricted to Firm 1 so the dedup target thread is visible to every user.
FIRM1_USERS = [f"firm1_member{m}@example.com" for m in (1, 2, 3, 4, 5)]


class _AuthedUser(HttpUser):
    """Login + sample-thread bootstrap. Subclasses override ``pick_email``."""

    abstract = True
    wait_time = between(0.5, 2.0)

    def pick_email(self) -> str:
        raise NotImplementedError

    def on_start(self) -> None:
        email = self.pick_email()
        resp = self.client.post(
            "/api/auth/token/",
            json={"email": email, "password": PASSWORD},
            name="POST /api/auth/token/",
        )
        if resp.status_code != 200:
            # Hard fail this user — login must succeed.
            self.environment.runner.quit()
            return
        data = resp.json()
        self.access = data["access"]
        self.refresh = data["refresh"]
        self.client.headers["Authorization"] = f"Bearer {self.access}"

        # Pull a few sample thread IDs so tasks have valid UUIDs to hit.
        resp = self.client.get("/api/threads/sample/", name="GET /api/threads/sample/")
        self.threads = [t["id"] for t in resp.json()] if resp.status_code == 200 else []


# ---------- Mixed read-heavy traffic (the realistic default) ----------------


class ReaderUser(_AuthedUser):
    """95-ish percent reads + occasional refresh — matches a typical accountant session."""

    weight = 9

    def pick_email(self) -> str:
        return random.choice(FIRM_USERS)

    @task(10)
    def get_summary(self):
        if not self.threads:
            return
        tid = random.choice(self.threads)
        with self.client.get(
            f"/api/threads/{tid}/summary/",
            name="GET /api/threads/{id}/summary/",
            catch_response=True,
        ) as r:
            # 404 with refresh_url is the correct response for "not generated yet" —
            # not an error, just a thread without a summary in the random sample.
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"unexpected status {r.status_code}")

    @task(5)
    def get_thread(self):
        if not self.threads:
            return
        tid = random.choice(self.threads)
        self.client.get(
            f"/api/threads/{tid}/",
            name="GET /api/threads/{id}/",
        )

    @task(1)
    def post_refresh(self):
        if not self.threads:
            return
        tid = random.choice(self.threads)
        self.client.post(
            f"/api/threads/{tid}/summary/refresh/",
            name="POST /api/threads/{id}/summary/refresh/",
        )


# ---------- Fan-in dedup proof ----------------------------------------------


class DedupHammerUser(_AuthedUser):
    """All users in this class hammer ONE thread — verifies fan-in.

    Look at the Locust UI:
      * "POST refresh (dedup target)" RPS should equal request volume.
      * Watch the Celery worker log: only a small fraction should actually run.
      * In the response body, the ``joined`` field should be ``true`` for most.
    """

    weight = 1
    wait_time = constant(0.1)  # maximize overlap
    _target_thread: str | None = None

    def pick_email(self) -> str:
        # Constrained to Firm 1 so every user can see the same target thread.
        return random.choice(FIRM1_USERS)

    def on_start(self) -> None:
        super().on_start()
        # Pick a shared target on first spawn; reuse for all subsequent users.
        if DedupHammerUser._target_thread is None and self.threads:
            DedupHammerUser._target_thread = self.threads[0]

    @task
    def hammer_refresh(self):
        target = DedupHammerUser._target_thread
        if not target:
            return
        with self.client.post(
            f"/api/threads/{target}/summary/refresh/",
            name="POST refresh (dedup target)",
            catch_response=True,
        ) as r:
            if r.status_code == 202:
                # joined=true is the expected outcome under load — fan-in worked.
                r.success()
            elif r.status_code == 429:
                # Hitting the 10/min/firm throttle is also a correct outcome.
                r.success()
            else:
                r.failure(f"unexpected status {r.status_code}: {r.text[:120]}")


# ---------- Reports under load ----------------------------------------------


class AdminReportUser(_AuthedUser):
    """Firm admin polling reports — exercises the aggregation + grouping path."""

    weight = 1

    def pick_email(self) -> str:
        return random.choice(FIRM_ADMINS)

    @task(3)
    def firm_report(self):
        self.client.get("/api/reports/firm/", name="GET /api/reports/firm/")

    @task(1)
    def firm_report_filtered(self):
        self.client.get(
            "/api/reports/firm/?since=2026-01-01T00:00:00Z",
            name="GET /api/reports/firm/ (since)",
        )


class SuperReportUser(_AuthedUser):
    """Single superuser polling the global aggregate report."""

    weight = 1

    def pick_email(self) -> str:
        return SUPERUSER

    @task
    def global_report(self):
        self.client.get("/api/reports/global/", name="GET /api/reports/global/")
