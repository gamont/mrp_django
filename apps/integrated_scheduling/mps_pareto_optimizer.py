from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from django.utils import timezone

from .models import MPSOptimizationPolicy, MPSRevisionOptimizationRun, MPSRevisionOptimizationCandidate, MPSRevisionOptimizationAction
from .mps_optimizer import _snapshot_lines, _overrides_from_lines, _evaluate_candidate, _score

D=Decimal

def ortools_pareto_available():
    try:
        from ortools.sat.python import cp_model  # noqa
        return True
    except Exception:
        return False

def _cp_model():
    try:
        from ortools.sat.python import cp_model
        return cp_model
    except Exception as exc:
        raise RuntimeError('OR-Tools não está disponível. Use a imagem Docker do projeto (ortools>=9.14,<10).') from exc

def _int(v, scale):
    return int((D(v or 0)*D(scale)).to_integral_value())

def _objective_profiles(limit):
    # Proxy objectives used only to generate diverse feasible MPS shapes. The real
    # MRP/RCCP/financial objectives are evaluated afterwards by the existing pipeline.
    profiles=[
        ('BALANCED', 10,10,4), ('MIN_CHANGE',30,4,2), ('LEVEL_LOAD',5,30,2),
        ('EARLY_BIAS',8,8,18), ('LATE_BIAS',8,8,-18), ('LEVEL_STRONG',2,50,0),
        ('CHANGE_LIGHT',3,12,0), ('BALANCED_2',12,16,4), ('EARLY_LIGHT',15,8,8),
        ('LATE_LIGHT',15,8,-8), ('SMOOTH',8,25,0), ('MIN_CHANGE_2',40,2,0),
    ]
    return profiles[:max(1,int(limit))]

def _build_solution(lines, policy, profile):
    cp_model=_cp_model(); model=cp_model.CpModel(); scale=int(policy.pareto_quantity_scale or 100)
    max_pct=D(policy.pareto_max_change_percent or 0)/D('100')
    vars_={}; groups=defaultdict(list); original={}
    for idx,x in enumerate(lines):
        cur=_int(x['quantity'],scale); original[idx]=cur; groups[x['item_id']].append(idx)
        if x['mps_status']=='FROZEN': lo=hi=cur
        else:
            band=max(1,int(abs(cur)*float(max_pct))) if cur else max(1,scale)
            lo=max(0,cur-band); hi=cur+band
        vars_[idx]=model.NewIntVar(lo,hi,f'q{idx}')
    # Preserve total volume per item; optimizer redistributes timing, not total S&OP demand.
    for _,idxs in groups.items(): model.Add(sum(vars_[i] for i in idxs)==sum(original[i] for i in idxs))
    absdev=[]; smooth=[]; time_expr=[]
    for i,v in vars_.items():
        d=model.NewIntVar(0,max(original[i]*2+scale,scale),f'd{i}'); model.AddAbsEquality(d,v-original[i]); absdev.append(d)
    for item_id,idxs in groups.items():
        idxs=sorted(idxs,key=lambda i:lines[i]['bucket_start'])
        for a,b in zip(idxs,idxs[1:]):
            maxv=max(original[a],original[b],scale)*3
            z=model.NewIntVar(0,maxv,f's{a}_{b}'); model.AddAbsEquality(z,vars_[a]-vars_[b]); smooth.append(z)
        for pos,i in enumerate(idxs): time_expr.append((pos+1)*vars_[i])
    name,w_change,w_smooth,w_time=profile
    # Positive time weight favors earlier buckets; negative favors later buckets.
    obj=w_change*sum(absdev)+(w_smooth*sum(smooth) if smooth else 0)+(w_time*sum(time_expr) if time_expr else 0)
    model.Minimize(obj)
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=float(policy.pareto_solver_time_limit_seconds or 20); solver.parameters.num_search_workers=8
    status=solver.Solve(model)
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None, solver.StatusName(status)
    out=[]
    for i,x in enumerate(lines):
        y=dict(x); y['quantity']=D(solver.Value(vars_[i]))/D(scale); out.append(y)
    return out, solver.StatusName(status)

def _service_proxy(candidate):
    raw=(candidate.planning_overrides or {}).get('candidate_mps_lines') or []
    # Estimated delayed volume vs source revision. It is intentionally not labelled OTIF:
    # actual OTIF requires real deliveries; this is a forward service-risk proxy.
    base={(x.item_id,x.bucket_start):D(x.quantity or 0) for x in candidate.optimization_run.revision.lines.all()}
    delayed=D('0'); cumulative_by_item=defaultdict(D); basecum=defaultdict(D)
    for x in sorted(raw,key=lambda r:(int(r['item_id']),r['bucket_start'])):
        iid=int(x['item_id']); q=D(str(x['quantity'])); b=base.get((iid, __import__('datetime').date.fromisoformat(x['bucket_start'])),D('0'))
        cumulative_by_item[iid]+=q; basecum[iid]+=b
        if cumulative_by_item[iid] < basecum[iid]: delayed += basecum[iid]-cumulative_by_item[iid]
    return delayed

def objective_vector(candidate):
    m=candidate.metrics or {}; n=lambda k:D(str(m.get(k) or 0))
    return {
        'service_risk_proxy':str(n('shortage_delta_count')+_service_proxy(candidate)),
        'shortage_delta':str(n('shortage_delta_count')),
        'rccp_overload_hours':str(n('rccp_overload_hours')),
        'peak_uncovered_financing':str(n('peak_uncovered_financing')),
        'interest_cost':str(n('interest_cost')),
        'inventory_exposure':str(n('inventory_exposure')),
        'purchase_spend':str(n('purchase_spend')),
        'peak_working_capital_need':str(n('peak_working_capital_need')),
    }

PARETO_KEYS=('service_risk_proxy','rccp_overload_hours','peak_uncovered_financing','interest_cost','inventory_exposure','purchase_spend')
def dominates(a,b):
    av=[D(str(a.get(k) or 0)) for k in PARETO_KEYS]; bv=[D(str(b.get(k) or 0)) for k in PARETO_KEYS]
    return all(x<=y for x,y in zip(av,bv)) and any(x<y for x,y in zip(av,bv))

def assign_pareto(candidates):
    remaining=list(candidates); front=1
    while remaining:
        current=[]
        for c in remaining:
            cv=c.objective_vector or {}
            if not any(other.id!=c.id and dominates(other.objective_vector or {},cv) for other in remaining): current.append(c)
        if not current: current=[remaining[0]]
        for c in current:
            all_others=[o for o in candidates if o.id!=c.id]
            count=sum(1 for o in all_others if dominates(o.objective_vector or {},c.objective_vector or {}))
            c.pareto_rank=front; c.is_pareto=(front==1); c.dominated_by_count=count
            c.save(update_fields=['pareto_rank','is_pareto','dominated_by_count','updated_at'])
        ids={c.id for c in current}; remaining=[c for c in remaining if c.id not in ids]; front+=1
    return [c for c in candidates if c.is_pareto]

def run_pareto_optimizer(optimization_run):
    run=MPSRevisionOptimizationRun.objects.select_related('revision__publication__cycle','compare_revision','created_by').get(pk=optimization_run.pk)
    policy,_=MPSOptimizationPolicy.objects.get_or_create(plant=run.revision.publication.cycle.plant)
    if not policy.enable_cp_sat_pareto: raise ValueError('CP-SAT Pareto está desabilitado na política da planta.')
    run.optimizer_mode='CP_SAT_PARETO'; run.status=run.Status.RUNNING; run.started_at=timezone.now(); run.error_message=''; run.save(update_fields=['optimizer_mode','status','started_at','error_message','updated_at'])
    try:
        lines=_snapshot_lines(run.revision); run.candidates.all().delete(); seen=set(); generated=[]; statuses=[]
        # Current revision is always included as an anchor.
        anchor=MPSRevisionOptimizationCandidate.objects.create(optimization_run=run,strategy=MPSRevisionOptimizationCandidate.Strategy.BASELINE,name='Plano atual / âncora',planning_overrides={})
        generated.append(anchor); seen.add('ANCHOR')
        for profile in _objective_profiles(max(1,policy.pareto_candidate_limit-1)):
            solved,status=_build_solution(lines,policy,profile); statuses.append(status)
            if not solved: continue
            ov=_overrides_from_lines(solved); signature=tuple((x['item_id'],x['bucket_start'],x['quantity']) for x in ov['candidate_mps_lines'])
            if signature in seen: continue
            seen.add(signature)
            c=MPSRevisionOptimizationCandidate.objects.create(optimization_run=run,strategy=MPSRevisionOptimizationCandidate.Strategy.CP_SAT_PARETO,name=f'CP-SAT {profile[0]}',planning_overrides=ov,notes='Candidato gerado por CP-SAT; objetivos reais são avaliados posteriormente pelo pipeline MRP/RCCP/financeiro.')
            generated.append(c)
            if len(generated)>=policy.pareto_candidate_limit: break
        evaluated=[]
        for c in generated:
            c=_evaluate_candidate(c,run.compare_revision,policy,run.created_by); c.objective_vector=objective_vector(c); c.save(update_fields=['objective_vector','updated_at']); evaluated.append(c)
        frontier=assign_pareto(evaluated)
        # Score remains only a tie-breaker within each Pareto layer; no single weighted score defines the frontier.
        ranked=sorted(evaluated,key=lambda c:(c.pareto_rank or 999,c.score if c.score is not None else D('1e30'),c.id))
        for idx,c in enumerate(ranked,1):
            c.rank=idx; c.is_recommended=(idx==1); c.save(update_fields=['rank','is_recommended','updated_at'])
        best=ranked[0] if ranked else None
        run.solver_status=','.join(sorted(set(statuses)))[:30]
        run.summary={'candidate_count':len(ranked),'pareto_frontier_count':len(frontier),'pareto_candidate_ids':[c.id for c in frontier],'recommended_candidate_id':best.id if best else None,'recommended_strategy':best.strategy if best else None,'optimizer_mode':'CP_SAT_PARETO','pareto_objectives':list(PARETO_KEYS),'service_metric_note':'service_risk_proxy é uma métrica prospectiva baseada em faltas e atraso relativo de volume; não é OTIF realizado, que exige entregas reais.','method':'CP-SAT gera distribuições MPS diversas preservando o volume total por item e congelando buckets FROZEN; cada candidato é então submetido ao pipeline completo MRP + RCCP + financeiro + capital de giro + financiamento. Dominância Pareto é calculada sobre métricas reais do what-if.','warning':'A fronteira Pareto apoia decisão humana. Nenhum candidato é publicado automaticamente.'}
        run.status=run.Status.COMPLETED; run.completed_at=timezone.now(); run.save(update_fields=['solver_status','summary','status','completed_at','updated_at']); return run
    except Exception as exc:
        run.status=run.Status.FAILED; run.error_message=str(exc); run.completed_at=timezone.now(); run.save(update_fields=['status','error_message','completed_at','updated_at']); raise
