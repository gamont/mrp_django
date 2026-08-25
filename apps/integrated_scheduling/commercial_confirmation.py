from __future__ import annotations

import json
from urllib import request as urlrequest
from urllib.error import URLError

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone

from .models import (
    CommercialCommunication, CommercialPromiseAlert, CommercialServiceCase,
    CustomerPromiseResponse, SalesOrderCommercialContact, SalesOrderPromise,
)


def effective_customer_commitment_date(line):
    """Data aceita pelo cliente; se não houver aceite, mantém a data contratual solicitada."""
    accepted = CustomerPromiseResponse.objects.filter(
        promise__sales_order_line=line,
        promise__status=SalesOrderPromise.Status.APPROVED,
        response=CustomerPromiseResponse.Response.ACCEPTED,
    ).exclude(confirmed_date__isnull=True).order_by("-received_at").first()
    return accepted.confirmed_date if accepted else line.requested_date


def _message_text(promise):
    line = promise.sales_order_line
    order = line.sales_order
    return (
        f"Pedido {order.number}, linha {line.line_number}, item {line.item.code}.\n"
        f"Nova data prometida proposta: {promise.proposed_date:%d/%m/%Y}.\n"
        f"Quantidade: {promise.quantity}.\n\n"
        "Solicitamos a confirmação desta nova data."
    )


@transaction.atomic
def send_promise_to_customer(promise, *, contact=None, actor=None, channel=None):
    promise = SalesOrderPromise.objects.select_for_update().select_related(
        "sales_order_line__sales_order", "sales_order_line__item"
    ).get(pk=promise.pk)
    if promise.status != SalesOrderPromise.Status.APPROVED:
        raise ValueError("Somente promessa internamente aprovada pode ser comunicada ao cliente.")
    order = promise.sales_order_line.sales_order
    contact = contact or order.commercial_contacts.filter(is_active=True).order_by("id").first()
    if not contact:
        raise ValueError("Pedido sem contato comercial ativo.")
    channel = channel or contact.preferred_channel
    key = f"promise:{promise.pk}:contact:{contact.pk}:{channel}:{promise.proposed_date.isoformat()}"
    obj, created = CommercialCommunication.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "promise": promise,
            "service_case": promise.service_cases.order_by("-created_at").first(),
            "contact": contact,
            "channel": channel,
            "subject": f"Confirmação de nova data — pedido {order.number}",
            "body": _message_text(promise),
            "payload": {"promise_id": promise.pk, "sales_order": order.number, "proposed_date": promise.proposed_date.isoformat()},
        },
    )
    if not created and obj.status == CommercialCommunication.Status.SENT:
        return obj
    try:
        if channel == SalesOrderCommercialContact.Channel.EMAIL:
            if not contact.email:
                raise ValueError("Contato sem e-mail cadastrado.")
            msg = EmailMultiAlternatives(
                subject=obj.subject,
                body=obj.body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "mrp@example.invalid"),
                to=[contact.email],
            )
            msg.send(fail_silently=False)
        elif channel == SalesOrderCommercialContact.Channel.API:
            if not contact.api_url:
                raise ValueError("Contato sem URL de API cadastrada.")
            data = json.dumps(obj.payload).encode("utf-8")
            req = urlrequest.Request(contact.api_url, data=data, headers={"Content-Type": "application/json", "Idempotency-Key": key}, method="POST")
            with urlrequest.urlopen(req, timeout=10) as resp:
                obj.external_reference = resp.headers.get("X-Request-Id", "")
        elif channel != SalesOrderCommercialContact.Channel.MANUAL:
            raise ValueError(f"Canal não suportado: {channel}")
        obj.status = CommercialCommunication.Status.SENT
        obj.sent_at = timezone.now()
        obj.error = ""
        obj.save(update_fields=["status", "sent_at", "error", "external_reference", "updated_at"])
        promise.service_cases.update(status=CommercialServiceCase.Status.WAITING_CUSTOMER, updated_at=timezone.now())
    except Exception as exc:
        obj.status = CommercialCommunication.Status.FAILED
        obj.error = str(exc)
        obj.save(update_fields=["status", "error", "updated_at"])
        raise
    return obj


@transaction.atomic
def record_customer_response(promise, *, response, actor=None, channel="MANUAL", confirmed_date=None, counterproposed_date=None, notes="", external_reference="", reevaluate=True):
    promise = SalesOrderPromise.objects.select_for_update().get(pk=promise.pk)
    if promise.status != SalesOrderPromise.Status.APPROVED:
        raise ValueError("A resposta do cliente exige uma promessa internamente aprovada.")
    response = CustomerPromiseResponse.Response(response)
    if response == CustomerPromiseResponse.Response.ACCEPTED and not confirmed_date:
        confirmed_date = promise.proposed_date
    if response == CustomerPromiseResponse.Response.COUNTERPROPOSED and not counterproposed_date:
        raise ValueError("Contraproposta exige counterproposed_date.")
    obj = CustomerPromiseResponse.objects.create(
        promise=promise, response=response, channel=channel, confirmed_date=confirmed_date,
        counterproposed_date=counterproposed_date, notes=notes, external_reference=external_reference,
        received_by=actor,
    )
    case = promise.service_cases.order_by("-created_at").first()
    if response == CustomerPromiseResponse.Response.ACCEPTED:
        if case:
            case.status = CommercialServiceCase.Status.CLOSED
            case.notes = (case.notes + f"\nCliente aceitou {confirmed_date}.").strip()
            case.save(update_fields=["status", "notes", "updated_at"])
        CommercialPromiseAlert.objects.filter(sales_order_line=promise.sales_order_line, status__in=["OPEN", "ACKNOWLEDGED"]).update(status="RESOLVED", updated_at=timezone.now())
    else:
        if case:
            case.status = CommercialServiceCase.Status.IN_REVIEW
            case.notes = (case.notes + f"\nCliente {response.lower()}: {notes}" ).strip()
            case.save(update_fields=["status", "notes", "updated_at"])
        if reevaluate:
            from .commercial_promising import evaluate_line_atp_ctp
            proposal = evaluate_line_atp_ctp(promise.sales_order_line, actor=actor, run_ctp=True)
            if counterproposed_date:
                proposal.rationale = (proposal.rationale + f"\nContraproposta do cliente: {counterproposed_date}.").strip()
                proposal.save(update_fields=["rationale", "updated_at"])
    return obj
