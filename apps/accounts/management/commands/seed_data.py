"""Idempotent seed command — populates Firms, Accountants, Clients, Threads, Messages.

Safe to re-run: uses ``get_or_create`` for entities and ``external_thread_id`` /
``external_message_id`` for de-dup on threads & messages. Outputs credentials and
sample thread IDs so the reviewer can curl immediately.
"""

import random
from datetime import timedelta, timezone

from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from apps.accounts.models import Accountant, Firm, RoleChoices
from apps.clients.models import Client
from apps.emails.models import EmailMessage, EmailThread

FAKER_SEED = 4242
RANDOM_SEED = 4242
PASSWORD = "Passw0rd!"  # noqa: S105 — seeded local dev only

# Realistic-shaped CPA correspondence so the LLM has actual structure to summarize.
# Bodies are short, mention concrete forms/deadlines/amounts, and balance between
# "ask" / "confirm" / "follow-up" so action_items + conclusions populate.
CLIENT_TEMPLATES = [
    (
        "Hi {accountant_first},\n\n"
        "Please find attached the {form} for FY{year}. Let me know if you need anything else "
        "before we finalize.\n\nThanks,\n{client_first}"
    ),
    (
        "Hi {accountant_first},\n\n"
        "Quick question — does the {expense} I paid last quarter qualify as a deductible "
        "business expense? Receipts are in the drive folder.\n\n"
        "{client_first}"
    ),
    (
        "Hi {accountant_first},\n\n"
        "Confirming — we're filing an extension and the new deadline is October 15, {year}, "
        "correct? I want to make sure I send the estimated payment in time.\n\n"
        "Best,\n{client_first}"
    ),
    (
        "Hello,\n\n"
        "I still haven't received the {form} from my broker. I'll forward it the moment it "
        "arrives. Is the {deadline} cutoff still firm?\n\n"
        "{client_first}"
    ),
    (
        "Hi {accountant_first},\n\n"
        "Need to update my mailing address on file for the {year} return — moved last month. "
        "Can you let me know what you need from me?\n\n"
        "{client_first}"
    ),
    (
        "Hi {accountant_first},\n\n"
        "Got it, thanks for the clarification. I'll send the {form} and the supporting "
        "statements by end of week.\n\n"
        "{client_first}"
    ),
]

ACCOUNTANT_TEMPLATES = [
    (
        "Hi {client_first},\n\n"
        "Received your {form} — thanks. I still need the {form2} before I can finalize the "
        "return. Could you send it by {deadline}?\n\n"
        "Best regards,\n{accountant_first}"
    ),
    (
        "Hi {client_first},\n\n"
        "Yes, {expense} qualifies as a deductible business expense as long as it's directly "
        "tied to business use. Hold on to the receipts in case of audit.\n\n"
        "Thanks,\n{accountant_first}"
    ),
    (
        "Hi {client_first},\n\n"
        "Confirming we've filed your extension. New filing deadline is October 15, {year}. "
        "Please send an estimated payment of ${amount:,} by the original April deadline to "
        "avoid penalties.\n\n"
        "{accountant_first}"
    ),
    (
        "Hi {client_first},\n\n"
        "Good news — your {year} return has been filed and accepted by the IRS. Expected "
        "refund of ${amount:,} should land in your account within 21 business days.\n\n"
        "Regards,\n{accountant_first}"
    ),
    (
        "Hi {client_first},\n\n"
        "Following up — we still don't have your {form}. Without it we can't proceed with "
        "the return. Please send by {deadline} so we stay on schedule.\n\n"
        "{accountant_first}"
    ),
    (
        "Hi {client_first},\n\n"
        "Quick update — finished reviewing the {form}. One item needs clarification: the "
        "${amount:,} entry under 'consulting income'. Can you confirm whether that was paid "
        "by a single payer or multiple?\n\n"
        "Thanks,\n{accountant_first}"
    ),
]

FORMS = [
    "K-1",
    "1099-MISC",
    "1099-NEC",
    "W-2",
    "1098",
    "Schedule C",
    "Schedule E",
    "Form 5498",
]
DEADLINES = ["March 31", "April 1", "April 5", "April 10", "April 15"]
EXPENSES = [
    "home office setup",
    "vehicle mileage",
    "client lunch",
    "software subscription",
    "conference travel",
    "professional development course",
]


class Command(BaseCommand):
    help = "Seed firms, accountants, clients, email threads and messages (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--firms",
            type=int,
            default=4,
            help="Number of firms (default 4).",
        )
        parser.add_argument(
            "--clients-per-firm",
            type=int,
            default=15,
            help="Clients per firm (default 15).",
        )
        parser.add_argument(
            "--threads-per-firm",
            type=int,
            default=25,
            help="Email threads per firm (default 25 → 100 total at 4 firms).",
        )

    def handle(self, *args, **opts):
        fake = Faker()
        Faker.seed(FAKER_SEED)
        random.seed(RANDOM_SEED)

        with transaction.atomic():
            superadmin = self._seed_superuser()
            firms = self._seed_firms(fake, count=opts["firms"])
            accountants_by_firm = self._seed_accountants(fake, firms)
            clients_by_firm = self._seed_clients(
                fake, firms, per_firm=opts["clients_per_firm"]
            )
            threads = self._seed_threads_and_messages(
                fake,
                clients_by_firm,
                accountants_by_firm,
                threads_per_firm=opts["threads_per_firm"],
            )

        self._print_summary(
            superadmin, firms, accountants_by_firm, clients_by_firm, threads
        )

    # --- Seeders ---------------------------------------------------------

    def _seed_superuser(self) -> Accountant:
        user, created = Accountant.objects.get_or_create(
            email="superadmin@example.com",
            defaults={
                "role": RoleChoices.SUPERUSER,
                "is_staff": True,
                "is_superuser": True,
                "firm": None,
            },
        )
        if created:
            user.set_password(PASSWORD)
            user.save(update_fields=["password"])
        return user

    def _seed_firms(self, fake: Faker, *, count: int) -> list[Firm]:
        firms: list[Firm] = []
        for i in range(count):
            name = f"{fake.company()} CPAs"
            firm, _ = Firm.objects.get_or_create(
                name=name,
                defaults={
                    "metadata": {
                        "region": fake.state(),
                        "tier": random.choice(["bronze", "silver", "gold"]),
                    }
                },
            )
            firms.append(firm)
        return firms

    def _seed_accountants(
        self, fake: Faker, firms: list[Firm]
    ) -> dict[Firm, list[Accountant]]:
        out: dict[Firm, list[Accountant]] = {}
        for idx, firm in enumerate(firms):
            slug = f"firm{idx + 1}"
            firm_accountants: list[Accountant] = []
            # 1 admin + 5 members.
            for role_idx, role in enumerate(
                [RoleChoices.ADMIN] + [RoleChoices.MEMBER] * 5,
            ):
                email = f"{slug}_{role.value}{role_idx}@example.com"
                user, created = Accountant.objects.get_or_create(
                    email=email,
                    defaults={
                        "firm": firm,
                        "role": role,
                        "first_name": fake.first_name(),
                        "last_name": fake.last_name(),
                        "is_staff": role == RoleChoices.ADMIN,
                    },
                )
                if created:
                    user.set_password(PASSWORD)
                    user.save(update_fields=["password"])
                firm_accountants.append(user)
            out[firm] = firm_accountants
        return out

    def _seed_clients(
        self,
        fake: Faker,
        firms: list[Firm],
        *,
        per_firm: int,
    ) -> dict[Firm, list[Client]]:
        out: dict[Firm, list[Client]] = {}
        for firm_idx, firm in enumerate(firms):
            firm_clients: list[Client] = []
            for c_idx in range(per_firm):
                # Deterministic external email so re-runs hit get_or_create.
                email = f"client{c_idx}@firm{firm_idx + 1}.example.com"
                client, _ = Client.objects.get_or_create(
                    firm=firm,
                    email=email,
                    defaults={"name": fake.name()},
                )
                firm_clients.append(client)
            out[firm] = firm_clients
        return out

    def _seed_threads_and_messages(
        self,
        fake: Faker,
        clients_by_firm: dict[Firm, list[Client]],
        accountants_by_firm: dict[Firm, list[Accountant]],
        *,
        threads_per_firm: int,
    ) -> list[EmailThread]:
        all_threads: list[EmailThread] = []

        # Edge-case distribution per firm: 1 single-msg, 1 forwarded, 1 multi-Cc, 1 long, 1 very-long, rest 3–8 msgs.
        edge_case_pattern = ["single", "forwarded", "multi_cc", "long", "very_long"]

        for firm_idx, (firm, clients) in enumerate(clients_by_firm.items()):
            accountants = accountants_by_firm[firm]
            for t_idx in range(threads_per_firm):
                # Pick edge case (5 special) or normal.
                if t_idx < len(edge_case_pattern):
                    kind = edge_case_pattern[t_idx]
                else:
                    kind = "normal"
                client = clients[t_idx % len(clients)]
                external_thread_id = f"thread-f{firm_idx + 1}-t{t_idx + 1}"

                # Idempotency: skip if thread already exists.
                if EmailThread.objects.filter(
                    external_thread_id=external_thread_id
                ).exists():
                    continue

                msg_count = self._message_count_for_kind(kind)
                first_at = fake.date_time_between(
                    start_date="-90d", end_date="-1d", tzinfo=timezone.utc
                )
                subject = self._subject_for_kind(fake, kind)

                thread = EmailThread.objects.create(
                    client=client,
                    firm=firm,
                    encrypted_subject=subject,
                    external_thread_id=external_thread_id,
                    first_message_at=first_at,
                    last_message_at=first_at,
                )
                last_sent = first_at
                for m_idx in range(msg_count):
                    sender, recipients, accountant = self._sender_recipients(
                        kind, m_idx, client, accountants
                    )
                    sent_at = last_sent + timedelta(hours=random.randint(1, 26))
                    body = self._render_body(
                        sender_is_client=(sender == client.email),
                        client=client,
                        accountant=accountant,
                    )
                    EmailMessage.objects.create(
                        thread=thread,
                        client=client,
                        firm=firm,
                        external_message_id=f"{external_thread_id}-m{m_idx + 1}",
                        sender_email=sender,
                        recipients=recipients,
                        encrypted_body=body,
                        sent_at=sent_at,
                    )
                    last_sent = sent_at
                thread.last_message_at = last_sent
                thread.save(update_fields=["last_message_at"])
                all_threads.append(thread)

        return all_threads

    # --- Helpers ---------------------------------------------------------

    def _message_count_for_kind(self, kind: str) -> int:
        return {
            "single": 1,
            "forwarded": random.randint(4, 7),
            "multi_cc": random.randint(3, 6),
            "long": random.randint(20, 30),
            "very_long": random.randint(50, 60),
            "normal": random.randint(3, 8),
        }[kind]

    def _subject_for_kind(self, fake: Faker, kind: str) -> str:
        base = fake.catch_phrase()
        if kind == "forwarded":
            return f"Fwd: Re: Re: {base}"
        return base

    def _sender_recipients(
        self,
        kind: str,
        m_idx: int,
        client: Client,
        accountants: list[Accountant],
    ) -> tuple[str, dict, Accountant]:
        # Alternate sender between client and accountants.
        primary_accountant = accountants[m_idx % len(accountants)]
        if m_idx % 2 == 0:
            sender = client.email
            to = [primary_accountant.email]
        else:
            sender = primary_accountant.email
            to = [client.email]

        cc: list[str] = []
        if kind == "multi_cc":
            # Cc-heavy: every accountant in the firm.
            cc = [a.email for a in accountants if a.email != sender]
        elif kind in ("long", "very_long") and m_idx % 3 == 0:
            cc = [accountants[(m_idx + 1) % len(accountants)].email]

        return sender, {"to": to, "cc": cc}, primary_accountant

    def _render_body(
        self,
        *,
        sender_is_client: bool,
        client: Client,
        accountant: Accountant,
    ) -> str:
        templates = CLIENT_TEMPLATES if sender_is_client else ACCOUNTANT_TEMPLATES
        tmpl = random.choice(templates)
        client_first = (client.name or "there").split()[0]
        accountant_first = accountant.first_name or "team"
        form, form2 = random.sample(FORMS, 2)
        return tmpl.format(
            client_first=client_first,
            accountant_first=accountant_first,
            form=form,
            form2=form2,
            year=random.choice(["2024", "2025"]),
            deadline=random.choice(DEADLINES),
            expense=random.choice(EXPENSES),
            amount=random.randint(500, 25_000),
        )

    def _print_summary(
        self,
        superadmin: Accountant,
        firms: list[Firm],
        accountants_by_firm: dict[Firm, list[Accountant]],
        clients_by_firm: dict[Firm, list[Client]],
        threads: list[EmailThread],
    ) -> None:
        bar = "=" * 70
        self.stdout.write(self.style.SUCCESS(f"\n{bar}\nSeed complete.\n{bar}"))
        self.stdout.write(f"  Firms:       {len(firms)}")
        self.stdout.write(
            f"  Accountants: {sum(len(v) for v in accountants_by_firm.values()) + 1} (+1 superuser)"
        )
        self.stdout.write(
            f"  Clients:     {sum(len(v) for v in clients_by_firm.values())}"
        )
        self.stdout.write(f"  Threads:     {EmailThread.objects.count()}")
        self.stdout.write(f"  Messages:    {EmailMessage.objects.count()}")

        self.stdout.write(
            self.style.WARNING(f"\n--- Login credentials (password: {PASSWORD}) ---")
        )
        self.stdout.write(f"  Superuser: {superadmin.email}")
        for firm, users in accountants_by_firm.items():
            admin = next((u for u in users if u.role == RoleChoices.ADMIN), users[0])
            member = next((u for u in users if u.role == RoleChoices.MEMBER), users[-1])
            self.stdout.write(
                f"  [{firm.name}] admin: {admin.email}   member: {member.email}"
            )

        if threads:
            self.stdout.write(
                self.style.WARNING("\n--- Sample thread IDs (3 per firm) ---")
            )
            for firm in firms:
                sample = list(
                    EmailThread.objects.filter(firm=firm).values_list("id", flat=True)[
                        :3
                    ]
                )
                self.stdout.write(
                    f"  [{firm.name}]: {', '.join(str(t) for t in sample)}"
                )
        self.stdout.write(bar)
