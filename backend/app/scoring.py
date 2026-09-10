"""
Control-Effectiveness risk scoring & attribution engine.

Implements PRD section 4:
  - asset_risk()            per-asset technical risk score
  - business_risk()         org-level rollup weighted by business impact
  - attribution()           baseline / target / measured / error decomposition,
                             with per-control marginal-contribution attribution

Design notes (see docs/technical-documentation.md for full rationale):
  - Every score carries a [low, point, high] confidence band. The band is not
    synthetic randomness -- it is derived from the actual evidence-confidence
    weighting of the controls that make up the score. A score built on
    stale/self-reported/missing evidence necessarily gets a wider band.
  - method_version is stamped on every computed value so historical
    comparisons are never silently distorted by a formula change.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from . import models

METHOD_VERSION = "v1.0"

# Human-readable labels for the internal source enum -- used anywhere a
# confidence/evidence note is rendered as a sentence, so the UI never leaks
# a raw snake_case value like "automated_scan" to a reader.
EVIDENCE_SOURCE_LABEL = {
    "automated_scan": "an automated scan",
    "third_party_audit": "a third-party audit",
    "manual_attestation": "a manual attestation",
}

# ---- evidence freshness / confidence -------------------------------------

# day-based thresholds (this is a periodic-refresh prototype, not streaming)
AUTOMATED_FRESH_DAYS = 2
AUTOMATED_AGING_DAYS = 14
MANUAL_FRESH_DAYS = 14
MANUAL_AGING_DAYS = 45

# confidence multiplier lookup: (freshness_state, source) -> confidence
CONFIDENCE_TABLE = {
    ("fresh", "automated_scan"): 1.0,
    ("fresh", "third_party_audit"): 1.0,
    ("fresh", "manual_attestation"): 0.7,
    ("aging", "automated_scan"): 0.85,
    ("aging", "third_party_audit"): 0.85,
    ("aging", "manual_attestation"): 0.5,
    ("stale", "automated_scan"): 0.3,
    ("stale", "third_party_audit"): 0.3,
    ("stale", "manual_attestation"): 0.2,
}

STATUS_WEIGHT = {
    "planned": 0.0,
    "in_progress": 0.7,   # scaled further by rollout_percentage
    "completed": 0.7,     # capped below "verified" until evidence confirms it
}
VERIFIED_STATUS_WEIGHT = 1.0

SEVERITY_NUM = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def freshness_state(evidence_ts: datetime, as_of: datetime, source: str) -> str:
    age_days = (as_of - evidence_ts).days
    if source == "manual_attestation":
        if age_days <= MANUAL_FRESH_DAYS:
            return "fresh"
        if age_days <= MANUAL_AGING_DAYS:
            return "aging"
        return "stale"
    else:
        if age_days <= AUTOMATED_FRESH_DAYS:
            return "fresh"
        if age_days <= AUTOMATED_AGING_DAYS:
            return "aging"
        return "stale"


@dataclass
class EvidenceState:
    has_evidence: bool
    freshness: str  # fresh | aging | stale | missing
    source: Optional[str]
    confidence: float  # 0..1
    verified: bool


def latest_evidence_state(db: Session, control_id: str, as_of: datetime) -> EvidenceState:
    rows = (
        db.query(models.Evidence)
        .filter(models.Evidence.control_id == control_id, models.Evidence.timestamp <= as_of)
        .order_by(models.Evidence.timestamp.desc())
        .all()
    )
    if not rows:
        return EvidenceState(has_evidence=False, freshness="missing", source=None, confidence=0.0, verified=False)

    latest = rows[0]
    fstate = freshness_state(latest.timestamp, as_of, latest.source)
    confidence = CONFIDENCE_TABLE.get((fstate, latest.source), 0.2)
    verified = latest.source in ("automated_scan", "third_party_audit") and latest.result == "pass" and fstate != "stale"
    return EvidenceState(has_evidence=True, freshness=fstate, source=latest.source, confidence=confidence, verified=verified)


@dataclass
class ControlEffect:
    control_id: str
    name: str
    status: str
    rollout_percentage: float
    evidence: EvidenceState
    effectiveness: float  # 0..1, confidence-weighted contribution


def historical_rollout_percentage(control: models.Control, as_of: date) -> float:
    """We only store *current* rollout_percentage, not a history of it. For an
    as_of date in the past, linearly interpolate from 0% at planned_date to the
    control's current rollout_percentage today -- a documented simplification
    (see docs/technical-documentation.md) rather than silently applying today's
    progress retroactively to historical/baseline scoring."""
    today = date.today()
    if as_of >= today or not control.planned_date:
        return control.rollout_percentage
    span = (today - control.planned_date).days
    if span <= 0:
        return control.rollout_percentage
    elapsed = (as_of - control.planned_date).days
    frac = max(0.0, min(1.0, elapsed / span))
    return control.rollout_percentage * frac


def control_effectiveness(
    control: models.Control, evidence: EvidenceState, as_of: date, override_confidence: Optional[float] = None
) -> float:
    """Confidence-weighted effectiveness of a single control, 0..1.

    `evidence` is the evidence state AS KNOWN AS OF `as_of` (the caller
    resolves it via latest_evidence_state(..., as_of)), so this naturally
    reconstructs history: a control isn't credited until proof of it exists
    at that point in time, and confidence rises/falls with how fresh and
    well-sourced that proof was at the time -- not just whether the status
    field says "completed". Only override_confidence (used for the
    current-day low/high bound calculation) is time-restricted by the caller.
    """
    if control.status == "planned":
        return 0.0

    if control.status == "in_progress":
        rollout = historical_rollout_percentage(control, as_of)
        return max(0.0, min(1.0, STATUS_WEIGHT["in_progress"] * (rollout / 100.0)))

    # status == "completed"
    if control.completion_date and control.completion_date > as_of:
        return 0.0  # not completed yet as of this date

    conf = override_confidence if override_confidence is not None else evidence.confidence
    if not evidence.has_evidence:
        # Failure state: "completed" with zero evidence gets no credit at all
        # unless the caller is explicitly asking for a best-case bound.
        conf = 0.0 if override_confidence is None else override_confidence
    base = VERIFIED_STATUS_WEIGHT if evidence.verified else STATUS_WEIGHT["completed"]
    return max(0.0, min(1.0, base * conf))


def applicable_controls(db: Session, asset: models.Asset, as_of: date) -> list[models.Control]:
    q = db.query(models.Control).filter(
        models.Control.org_id == asset.org_id,
        (models.Control.scope_asset_id == asset.id) | (models.Control.scope_zone == asset.zone),
    )
    out = []
    for c in q.all():
        if c.planned_date and c.planned_date > as_of:
            continue  # doesn't exist yet as of this date
        out.append(c)
    return out


def resolved_criticality(asset: models.Asset) -> Optional[int]:
    if asset.criticality_resolved is not None:
        return asset.criticality_resolved
    if asset.criticality_scanner == asset.criticality_cmdb:
        return asset.criticality_scanner
    return None  # unresolved conflict -> caller must handle


def exposure_factor(db: Session, asset_id: str, as_of: date) -> float:
    vulns = db.query(models.Vulnerability).filter(
        models.Vulnerability.asset_id == asset_id,
        models.Vulnerability.discovered_date <= as_of,
    ).all()
    total = 0.0
    for v in vulns:
        is_open = v.status == "open" and (v.resolved_date is None or v.resolved_date > as_of)
        if v.status == "mitigated" and v.resolved_date and v.resolved_date > as_of:
            is_open = True  # wasn't mitigated yet as of this date
        if not is_open:
            continue
        age_days = (as_of - v.discovered_date).days
        age_factor = 1.0 if age_days < 30 else (1.3 if age_days < 90 else 1.6)
        total += (v.cvss / 10.0) * age_factor
    return min(total, 5.0)


def incident_multiplier(db: Session, asset_id: str, as_of: date) -> float:
    window_start = as_of - timedelta(days=90)
    incidents = db.query(models.Incident).filter(
        models.Incident.asset_id == asset_id,
        models.Incident.detected_date <= as_of,
        models.Incident.detected_date >= window_start,
    ).all()
    count = 0
    for i in incidents:
        if i.resolved_date is None or i.resolved_date > as_of:
            count += 1
        else:
            count += 0.5  # resolved incidents still count, but half as much
    return 1.0 + 0.15 * count


@dataclass
class AssetRiskResult:
    asset_id: str
    raw_score: float
    criticality_used: int
    criticality_conflict: bool
    exposure: float
    control_effect_avg: float
    incident_mult: float
    controls: list[ControlEffect] = field(default_factory=list)
    missing_telemetry: bool = False


def asset_risk(db: Session, asset: models.Asset, as_of: date, confidence_bias: Optional[str] = None) -> AssetRiskResult:
    """
    confidence_bias: None (point estimate), "low" (worst case: force confidence
    to the low bound for unresolved/low-confidence evidence), "high" (best case:
    assume full confidence on everything that has *any* evidence, i.e. audit
    would fully vindicate it).
    """
    crit = resolved_criticality(asset)
    conflict = crit is None
    crit_value = crit if crit is not None else min(asset.criticality_scanner or 3, asset.criticality_cmdb or 3)
    # unresolved conflicts are scored using the MORE conservative (higher) criticality
    # until resolved, so risk is never silently understated
    if conflict:
        crit_value = max(asset.criticality_scanner or 3, asset.criticality_cmdb or 3)

    if not asset.has_telemetry:
        # Failure state: asset has no monitoring feed at all. We do NOT default
        # this to "low risk" -- absence of visibility is itself risk-bearing.
        exp = 2.5  # neutral-elevated assumption, documented in UI as "unmonitored"
        controls: list[ControlEffect] = []
        eff_avg = 0.0
        inc_mult = 1.0
        missing_tel = True
    else:
        exp = exposure_factor(db, asset.id, as_of)
        ctrls = applicable_controls(db, asset, as_of)
        controls = []
        eff_sum = 0.0
        as_of_dt = datetime.combine(as_of, datetime.min.time())
        for c in ctrls:
            if c.completion_date and c.completion_date > as_of:
                ev = EvidenceState(False, "missing", None, 0.0, False)
            else:
                ev = latest_evidence_state(db, c.id, as_of_dt)
            override = None
            if as_of >= date.today():
                if confidence_bias == "low":
                    override = 0.0 if ev.freshness in ("stale", "missing") else min(ev.confidence, 0.5)
                elif confidence_bias == "high":
                    override = 1.0 if ev.has_evidence or c.status != "completed" else 0.0
            e = control_effectiveness(c, ev, as_of, override_confidence=override)
            controls.append(ControlEffect(c.id, c.name, c.status, c.rollout_percentage, ev, e))
            eff_sum += e
        eff_avg = (eff_sum / len(controls)) if controls else 0.0
        inc_mult = incident_multiplier(db, asset.id, as_of)
        missing_tel = False

    raw = crit_value * exp * (1 - eff_avg) * inc_mult
    return AssetRiskResult(
        asset_id=asset.id,
        raw_score=raw,
        criticality_used=crit_value,
        criticality_conflict=conflict,
        exposure=exp,
        control_effect_avg=eff_avg,
        incident_mult=inc_mult,
        controls=controls,
        missing_telemetry=missing_tel,
    )


# theoretical worst case per asset, used to normalize business risk to a 0-100 index
MAX_CRIT = 5
MAX_EXPOSURE = 5.0
MAX_INCIDENT_MULT = 1.6


def max_reference_score(db: Session, org_id: str) -> float:
    assets = db.query(models.Asset).filter(models.Asset.org_id == org_id).all()
    total = 0.0
    for a in assets:
        total += MAX_CRIT * MAX_EXPOSURE * 1.0 * MAX_INCIDENT_MULT * a.business_impact_weight
    return max(total, 1e-6)


@dataclass
class BusinessRiskResult:
    org_id: str
    as_of_date: date
    raw_score: float
    normalized_score: float  # 0-100 risk index
    asset_results: dict


def business_risk(db: Session, org_id: str, as_of: date, confidence_bias: Optional[str] = None) -> BusinessRiskResult:
    assets = db.query(models.Asset).filter(models.Asset.org_id == org_id).all()
    total = 0.0
    per_asset = {}
    for a in assets:
        r = asset_risk(db, a, as_of, confidence_bias=confidence_bias)
        weighted = r.raw_score * a.business_impact_weight
        per_asset[a.id] = (r, weighted)
        total += weighted
    ref = max_reference_score(db, org_id)
    normalized = min(100.0, (total / ref) * 100.0)
    return BusinessRiskResult(org_id=org_id, as_of_date=as_of, raw_score=total, normalized_score=normalized, asset_results=per_asset)


# Even a fully executed, fully verified control plan doesn't drive risk to
# literal zero (undetected/zero-day exposure, human error, etc.) -- capping
# the target's effectiveness keeps the ceiling credible instead of implying
# a perfect security program is achievable.
TARGET_MAX_EFFECTIVENESS = 0.9


def target_business_risk(db: Session, org_id: str, as_of: date) -> BusinessRiskResult:
    """Hypothetical best case: every control currently planned, in-progress, or
    completed for this org reaches verified status. Represents the ceiling of
    achievable risk reduction for the *current* control plan -- it does not
    invent new controls, only assumes the existing plan is fully executed."""
    assets = db.query(models.Asset).filter(models.Asset.org_id == org_id).all()
    total = 0.0
    per_asset = {}
    for a in assets:
        crit = resolved_criticality(a)
        crit_value = crit if crit is not None else max(a.criticality_scanner or 3, a.criticality_cmdb or 3)
        if not a.has_telemetry:
            exp = 2.5
            eff_avg = TARGET_MAX_EFFECTIVENESS  # target assumes telemetry gap gets fixed too
            inc_mult = 1.0
        else:
            exp = exposure_factor(db, a.id, as_of)
            # unlike measured/baseline scoring, target includes the FULL control
            # plan regardless of planned_date -- it represents "if the plan we
            # already have finishes," not just what's technically live today
            ctrls = db.query(models.Control).filter(
                models.Control.org_id == a.org_id,
                (models.Control.scope_asset_id == a.id) | (models.Control.scope_zone == a.zone),
            ).all()
            eff_avg = TARGET_MAX_EFFECTIVENESS if ctrls else 0.0
            inc_mult = 1.0  # target assumes incidents are prevented
        raw = crit_value * exp * (1 - eff_avg) * inc_mult
        weighted = raw * a.business_impact_weight
        per_asset[a.id] = (raw, weighted)
        total += weighted
    ref = max_reference_score(db, org_id)
    normalized = min(100.0, (total / ref) * 100.0)
    return BusinessRiskResult(org_id=org_id, as_of_date=as_of, raw_score=total, normalized_score=normalized, asset_results=per_asset)


@dataclass
class ControlAttributionResult:
    control_id: str
    name: str
    control_type: str
    status: str
    delta_low: float
    delta_point: float
    delta_high: float
    confidence_note: str


@dataclass
class AttributionSummary:
    org_id: str
    baseline: BusinessRiskResult
    target: BusinessRiskResult
    measured_point: BusinessRiskResult
    measured_low: BusinessRiskResult
    measured_high: BusinessRiskResult
    reduction_point: float
    reduction_pct: float
    reduction_low: float
    reduction_high: float
    pct_of_target_achieved: float
    per_control: list
    residual: float
    method_version: str = METHOD_VERSION


def _business_risk_excluding_control(db: Session, org_id: str, as_of: date, excluded_control_id: str) -> float:
    assets = db.query(models.Asset).filter(models.Asset.org_id == org_id).all()
    total = 0.0
    for a in assets:
        if not a.has_telemetry:
            r = asset_risk(db, a, as_of)
            total += r.raw_score * a.business_impact_weight
            continue
        crit = resolved_criticality(a)
        crit_value = crit if crit is not None else max(a.criticality_scanner or 3, a.criticality_cmdb or 3)
        exp = exposure_factor(db, a.id, as_of)
        ctrls = applicable_controls(db, a, as_of)
        as_of_dt = datetime.combine(as_of, datetime.min.time())
        eff_sum = 0.0
        n = 0
        for c in ctrls:
            n += 1
            if c.id == excluded_control_id:
                eff_sum += 0.0  # counterfactual: this control never happened
                continue
            ev = latest_evidence_state(db, c.id, as_of_dt)
            eff_sum += control_effectiveness(c, ev, as_of)
        eff_avg = (eff_sum / n) if n else 0.0
        inc_mult = incident_multiplier(db, a.id, as_of)
        raw = crit_value * exp * (1 - eff_avg) * inc_mult
        total += raw * a.business_impact_weight
    return total


def compute_attribution(db: Session, org_id: str, baseline_date: date, as_of: date) -> AttributionSummary:
    baseline = business_risk(db, org_id, baseline_date)
    target = target_business_risk(db, org_id, as_of)
    measured_point = business_risk(db, org_id, as_of, confidence_bias=None)
    measured_low = business_risk(db, org_id, as_of, confidence_bias="low")   # worst case -> HIGHEST residual risk
    measured_high = business_risk(db, org_id, as_of, confidence_bias="high")  # best case -> LOWEST residual risk

    reduction_point = baseline.raw_score - measured_point.raw_score
    reduction_low = baseline.raw_score - measured_high.raw_score   # largest reduction (best case: measured_high = lowest risk)
    reduction_high = baseline.raw_score - measured_low.raw_score   # smallest/negative reduction (worst case: measured_low = highest risk)
    reduction_pct = (reduction_point / baseline.raw_score * 100.0) if baseline.raw_score else 0.0
    achievable = baseline.raw_score - target.raw_score
    pct_of_target = (reduction_point / achievable * 100.0) if achievable > 1e-9 else 0.0

    completed_controls = db.query(models.Control).filter(
        models.Control.org_id == org_id, models.Control.status == "completed"
    ).all()

    per_control = []
    attributed_sum = 0.0
    for c in completed_controls:
        with_control = measured_point.raw_score
        without_control = _business_risk_excluding_control(db, org_id, as_of, c.id)
        delta_point = without_control - with_control  # risk this control is currently preventing

        as_of_dt = datetime.combine(as_of, datetime.min.time())
        ev = latest_evidence_state(db, c.id, as_of_dt)
        if ev.freshness == "missing":
            note = "No verification evidence on file -- excluded from risk credit, shown as zero."
            delta_low, delta_high = 0.0, 0.0
            delta_point = 0.0
        elif ev.freshness == "stale":
            note = f"Last checked a while ago (via {EVIDENCE_SOURCE_LABEL.get(ev.source, ev.source)}); reduction credit heavily discounted."
            delta_low = delta_point * 0.2
            delta_high = delta_point * 1.4
        elif ev.source == "manual_attestation":
            note = "Self-attested only, not independently verified; wide confidence band."
            delta_low = delta_point * 0.5
            delta_high = delta_point * 1.2
        else:
            note = "Independently verified by automated scan or audit."
            delta_low = delta_point * 0.9
            delta_high = delta_point * 1.05

        attributed_sum += delta_point
        per_control.append(ControlAttributionResult(
            control_id=c.id, name=c.name, control_type=c.control_type, status=c.status,
            delta_low=round(delta_low, 2), delta_point=round(delta_point, 2), delta_high=round(delta_high, 2),
            confidence_note=note,
        ))

    per_control.sort(key=lambda x: x.delta_point, reverse=True)
    residual = reduction_point - attributed_sum

    return AttributionSummary(
        org_id=org_id,
        baseline=baseline, target=target,
        measured_point=measured_point, measured_low=measured_low, measured_high=measured_high,
        reduction_point=round(reduction_point, 2),
        reduction_pct=round(reduction_pct, 1),
        reduction_low=round(reduction_low, 2),
        reduction_high=round(reduction_high, 2),
        pct_of_target_achieved=round(pct_of_target, 1),
        per_control=per_control,
        residual=round(residual, 2),
    )
