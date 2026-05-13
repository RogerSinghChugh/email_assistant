"""Shared factory_boy factories."""

import factory
from django.utils import timezone

from apps.accounts.models import Accountant, Firm, RoleChoices
from apps.clients.models import Client
from apps.emails.models import EmailMessage, EmailThread
from apps.summaries.models import EmailSummary


class FirmFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Firm
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Firm {n}")


class AccountantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Accountant
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    firm = factory.SubFactory(FirmFactory)
    role = RoleChoices.MEMBER
    password = factory.PostGenerationMethodCall("set_password", "Passw0rd!")


class ClientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Client

    name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"client{n}@example.com")
    firm = factory.SubFactory(FirmFactory)


class EmailThreadFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailThread

    client = factory.SubFactory(ClientFactory)
    firm = factory.LazyAttribute(lambda o: o.client.firm)
    encrypted_subject = factory.Faker("sentence", nb_words=4)
    external_thread_id = factory.Sequence(lambda n: f"ext-thread-{n}")
    first_message_at = factory.LazyFunction(timezone.now)
    last_message_at = factory.LazyFunction(timezone.now)


class EmailMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailMessage

    thread = factory.SubFactory(EmailThreadFactory)
    client = factory.LazyAttribute(lambda o: o.thread.client)
    firm = factory.LazyAttribute(lambda o: o.thread.firm)
    external_message_id = factory.Sequence(lambda n: f"ext-msg-{n}")
    sender_email = factory.Faker("email")
    recipients = factory.LazyFunction(lambda: {"to": ["a@x.com"], "cc": []})
    encrypted_body = factory.Faker("paragraph")
    sent_at = factory.LazyFunction(timezone.now)


class EmailSummaryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailSummary

    thread = factory.SubFactory(EmailThreadFactory)
    firm = factory.LazyAttribute(lambda o: o.thread.firm)
    encrypted_payload = factory.LazyFunction(
        lambda: {"actors": [], "conclusions": [], "action_items": []},
    )
    emails_analyzed = 0
    last_refreshed_at = factory.LazyFunction(timezone.now)
