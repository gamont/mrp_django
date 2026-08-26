from __future__ import annotations
import hashlib, hmac, json
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import MPSDecisionApprovalMatrix, MPSDecisionApprovalRequirement, MPSDecisionElectronicSignature

D=Decimal
LEVEL_RANK={"MANAGER":10,"DIRECTOR":20,"EXECUTIVE_COMMITTEE":30}
CONFIRMATION="APROVAR MPS"

def _d(v):
    try:return D(str(v or 0))
    except:return D('0')

def exposure_for(cockpit):
    c=cockpit.selected_candidate
    ov=(c.objective_vector or {}) if c else {}
    m=(c.metrics or {}) if c else {}
    return {
        'purchase_spend':str(_d(ov.get('purchase_spend',m.get('purchase_spend')))),
        'peak_working_capital_need':str(_d(ov.get('peak_working_capital_need',m.get('peak_working_capital_need')))),
        'peak_financing_need':str(_d(ov.get('peak_uncovered_financing',m.get('peak_uncovered_financing')))),
        'service_risk_proxy':str(_d(ov.get('service_risk_proxy',m.get('shortage_delta_count')))),
        'candidate_id':getattr(c,'id',None),
        'simulation_id':getattr(c,'simulation_id',None),
    }

def _matches(rule, e):
    tests=[]
    for rv,ev in [(rule.min_purchase_spend,e['purchase_spend']),(rule.min_peak_working_capital,e['peak_working_capital_need']),(rule.min_peak_financing_need,e['peak_financing_need']),(rule.min_service_risk_proxy,e['service_risk_proxy'])]:
        if _d(rv)>0: tests.append(_d(ev)>=_d(rv))
    return any(tests) if tests else bool(rule.is_default)

def select_rule(cockpit):
    plant=cockpit.publication.cycle.plant
    e=exposure_for(cockpit)
    rules=list(MPSDecisionApprovalMatrix.objects.filter(plant=plant,is_active=True))
    matched=[r for r in rules if _matches(r,e)]
    if matched:
        matched.sort(key=lambda r:(LEVEL_RANK.get(r.level,0),r.priority,r.id),reverse=True)
        return matched[0],e
    defaults=[r for r in rules if r.is_default]
    if defaults:
        defaults.sort(key=lambda r:(LEVEL_RANK.get(r.level,0),r.priority),reverse=True)
        return defaults[0],e
    return None,e

def decision_content(cockpit, exposure, rule=None):
    c=cockpit.selected_candidate
    return {'cockpit_id':cockpit.id,'publication_id':cockpit.publication_id,'candidate_id':getattr(c,'id',None),'candidate_objective_vector':(c.objective_vector or {}) if c else {},'selection_rationale':cockpit.selection_rationale,'exposure':exposure,'authority_level':getattr(rule,'level',None),'matrix_rule_id':getattr(rule,'id',None)}

def content_hash(cockpit, exposure, rule=None):
    raw=json.dumps(decision_content(cockpit,exposure,rule),sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()
    return hashlib.sha256(raw).hexdigest()

@transaction.atomic
def initialize_authority_requirements(cockpit):
    rule,e=select_rule(cockpit)
    cockpit.authority_requirements.filter(status=MPSDecisionApprovalRequirement.Status.PENDING).update(status=MPSDecisionApprovalRequirement.Status.SUPERSEDED)
    if not rule:
        return None
    h=content_hash(cockpit,e,rule)
    req=MPSDecisionApprovalRequirement.objects.create(cockpit=cockpit,matrix_rule=rule,level=rule.level,required_groups=rule.required_groups or [],required_signatures=max(1,rule.required_signatures),exposure_snapshot=e,decision_content_hash=h)
    from .mps_decision_audit import append_audit_event
    append_audit_event(cockpit, "AUTHORITY_CREATED", None, {"requirement_id": req.id, "level": req.level, "required_signatures": req.required_signatures, "decision_content_hash": h})
    return req

def _eligible(req,user):
    if not user or not getattr(user,'is_authenticated',False): return False
    groups=req.required_groups or []
    if not groups: return True
    return user.groups.filter(name__in=groups).exists() or bool(getattr(user,'is_superuser',False))

def _sig_hash(req,user,signed_at,content_h):
    msg=f'{req.id}|{user.id}|{signed_at.isoformat()}|{content_h}|APP-HMAC-SHA256-V1'.encode()
    return hmac.new(settings.SECRET_KEY.encode(),msg,hashlib.sha256).hexdigest()

@transaction.atomic
def sign_requirement(req,user,password=None,confirmation='',client_ip=None,user_agent=''):
    req=MPSDecisionApprovalRequirement.objects.select_for_update(of=('self',)).select_related('cockpit','matrix_rule').get(pk=req.pk)
    if req.status!=MPSDecisionApprovalRequirement.Status.PENDING: raise ValueError('A exigência de alçada não está pendente.')
    if (confirmation or '').strip().upper()!=CONFIRMATION: raise ValueError(f'Digite exatamente "{CONFIRMATION}" para confirmar a aprovação.')
    if not _eligible(req,user): raise ValueError('Usuário não pertence a um grupo autorizado para esta alçada.')
    if user.has_usable_password():
        if not password or not user.check_password(password): raise ValueError('Reautenticação por senha inválida.')
        auth=MPSDecisionElectronicSignature.AuthenticationMethod.PASSWORD
    else:
        auth=MPSDecisionElectronicSignature.AuthenticationMethod.SESSION
    current=content_hash(req.cockpit,req.exposure_snapshot,req.matrix_rule)
    if current!=req.decision_content_hash: raise ValueError('O conteúdo da decisão mudou; gere novamente a exigência de aprovação.')
    now=timezone.now(); groups=list(user.groups.values_list('name',flat=True))
    sig=MPSDecisionElectronicSignature.objects.create(requirement=req,signer=user,authentication_method=auth,confirmation_statement=CONFIRMATION,signed_at=now,content_hash=current,signature_hash=_sig_hash(req,user,now,current),signer_username=user.get_username(),signer_groups=groups,client_ip=client_ip,user_agent=(user_agent or '')[:300])
    if req.signatures.count()>=req.required_signatures:
        req.status=MPSDecisionApprovalRequirement.Status.SATISFIED; req.satisfied_at=now; req.save(update_fields=['status','satisfied_at','updated_at'])
    from .mps_decision_audit import append_audit_event
    append_audit_event(req.cockpit, "ELECTRONIC_SIGNATURE", user, {"requirement_id": req.id, "level": req.level, "signature_id": sig.id, "content_hash": sig.content_hash, "signature_hash": sig.signature_hash, "signature_version": sig.signature_version})
    return sig

def verify_signature(sig):
    expected=_sig_hash(sig.requirement,sig.signer,sig.signed_at,sig.content_hash)
    return hmac.compare_digest(expected,sig.signature_hash)

def authority_check(cockpit):
    req=cockpit.authority_requirements.filter(status__in=[MPSDecisionApprovalRequirement.Status.PENDING,MPSDecisionApprovalRequirement.Status.SATISFIED]).order_by('-created_at').first()
    if not req: return {'ok':True,'blockers':[],'requirement_id':None,'note':'Nenhuma matriz de alçada ativa se aplica.'}
    blockers=[]
    valid=sum(1 for s in req.signatures.select_related('signer').all() if verify_signature(s))
    if req.status!=MPSDecisionApprovalRequirement.Status.SATISFIED or valid<req.required_signatures:
        blockers.append(f'Alçada {req.get_level_display()} exige {req.required_signatures} assinatura(s); válidas: {valid}.')
    return {'ok':not blockers,'blockers':blockers,'requirement_id':req.id,'level':req.level,'valid_signatures':valid,'required_signatures':req.required_signatures,'exposure':req.exposure_snapshot}
