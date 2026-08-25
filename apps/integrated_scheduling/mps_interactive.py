from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import OperationalMPSPublication, MPSWeeklyBucket, MPSBucketChangeRequest
from .sop_mps import run_rccp

Q = Decimal('0.0001')
def q(v): return Decimal(v or 0).quantize(Q)

def _editable(pub):
    if pub.status not in [OperationalMPSPublication.Status.DRAFT, OperationalMPSPublication.Status.VALIDATED, OperationalMPSPublication.Status.BLOCKED]:
        raise ValueError('Somente MPS ainda não publicados podem ser alterados.')

def _violation(*buckets):
    return MPSBucketChangeRequest.Violation.FROZEN_BUCKET if any(b and b.mps_status == 'FROZEN' for b in buckets) else MPSBucketChangeRequest.Violation.NONE

@transaction.atomic
def request_bucket_edit(bucket, new_quantity, user=None, reason=''):
    bucket = MPSWeeklyBucket.objects.select_for_update().select_related('publication').get(pk=bucket.pk)
    _editable(bucket.publication)
    new_quantity=q(new_quantity)
    if new_quantity < 0: raise ValueError('Quantidade não pode ser negativa.')
    violation=_violation(bucket)
    req=MPSBucketChangeRequest.objects.create(publication=bucket.publication, source_bucket=bucket,
        source_quantity_before=bucket.quantity, source_quantity_after=new_quantity, violation=violation,
        reason=reason, requested_by=user)
    if violation == MPSBucketChangeRequest.Violation.NONE:
        _apply(req, user, 'Alteração fora do frozen horizon; aprovação automática.')
    return req

@transaction.atomic
def request_volume_move(source, target, quantity, user=None, reason=''):
    ids=sorted([source.pk,target.pk]); locked={b.pk:b for b in MPSWeeklyBucket.objects.select_for_update().filter(pk__in=ids).select_related('publication','item')}
    source,target=locked[source.pk],locked[target.pk]
    if source.publication_id != target.publication_id or source.item_id != target.item_id:
        raise ValueError('Movimentação exige mesmo MPS e mesmo item.')
    _editable(source.publication); quantity=q(quantity)
    if quantity <= 0 or quantity > source.quantity: raise ValueError('Quantidade de movimentação inválida.')
    req=MPSBucketChangeRequest.objects.create(publication=source.publication, source_bucket=source,target_bucket=target,
        source_quantity_before=source.quantity,source_quantity_after=q(source.quantity-quantity),
        target_quantity_before=target.quantity,target_quantity_after=q(target.quantity+quantity),
        violation=_violation(source,target),reason=reason,requested_by=user)
    if req.violation == MPSBucketChangeRequest.Violation.NONE:
        _apply(req,user,'Movimentação fora do frozen horizon; aprovação automática.')
    return req

def _apply(req,user=None,notes=''):
    src=MPSWeeklyBucket.objects.select_for_update().get(pk=req.source_bucket_id)
    src.quantity=req.source_quantity_after; src.save(update_fields=['quantity','updated_at'])
    if req.target_bucket_id:
        tgt=MPSWeeklyBucket.objects.select_for_update().get(pk=req.target_bucket_id)
        tgt.quantity=req.target_quantity_after; tgt.save(update_fields=['quantity','updated_at'])
    req.status=MPSBucketChangeRequest.Status.APPROVED; req.decided_by=user; req.decided_at=timezone.now(); req.decision_notes=notes
    req.save(update_fields=['status','decided_by','decided_at','decision_notes','updated_at'])
    run_rccp(req.publication)
    from .mps_revision import capture_revision
    capture_revision(req.publication, req.decided_by or req.requested_by, label=f'Alteração aprovada #{req.pk}', notes=req.reason)
    return req

@transaction.atomic
def approve_change(req,user=None,notes=''):
    req=MPSBucketChangeRequest.objects.select_for_update().get(pk=req.pk)
    if req.status != MPSBucketChangeRequest.Status.PENDING: raise ValueError('Solicitação não está pendente.')
    if user and req.requested_by_id and req.requested_by_id == user.id: raise ValueError('Alteração em zona congelada exige aprovação por outro usuário.')
    return _apply(req,user,notes)

@transaction.atomic
def reject_change(req,user=None,notes=''):
    req=MPSBucketChangeRequest.objects.select_for_update().get(pk=req.pk)
    if req.status != MPSBucketChangeRequest.Status.PENDING: raise ValueError('Solicitação não está pendente.')
    req.status=MPSBucketChangeRequest.Status.REJECTED; req.decided_by=user; req.decided_at=timezone.now(); req.decision_notes=notes
    req.save(update_fields=['status','decided_by','decided_at','decision_notes','updated_at']); return req

def bucket_delta(bucket):
    return q(bucket.quantity - bucket.baseline_quantity)
