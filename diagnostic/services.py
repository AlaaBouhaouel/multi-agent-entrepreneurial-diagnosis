from projects.models import ProfileLog, ProjectProfile
from criteria.criteria_nested import get_stage_criteria, is_leaf, STAGE_ORDER, BLOCKER_DOMAINS, get_stage_index
from calculations import _get_profile_value, _to_float, _is_truthy
from datetime import datetime, timezone


def _rollup(results, rule):
    # "all": any False → False | no False + any None → None | all True → True
    # "any": any True  → True  | all False → False          | otherwise → None
    if rule == "all":
        if any(r is False for r in results):  return False
        if any(r is None  for r in results):  return None
        return True
    if rule == "any":
        if any(r is True  for r in results):  return True
        if all(r is False for r in results):  return False
        return None
    return None


def _evaluate_leaf(leaf, profile):
    rule  = leaf.get("rule")

    # field_group: check multiple fields with the leaf's own rule
    if "field_group" in leaf:
        results = [_is_truthy(_get_profile_value(profile, f)) for f in leaf["field_group"]]
        return _rollup(results, rule)

    field = leaf.get("field")
    value = _get_profile_value(profile, field)

    if rule == "truthy":
        return _is_truthy(value)

    if rule == "enum_in":
        if value is None: return None
        return value in leaf.get("allowed_values", [])

    if rule == "min_value":
        num = _to_float(value)
        if num is None: return None
        return num >= leaf["min_value"]

    if rule == "contains":
        if value is None: return None
        target = leaf.get("value")
        return target in value   # works for list or str

    return None


def _evaluate_node(node, profile):
    if is_leaf(node):
        return _evaluate_leaf(node, profile)

    child_results = [_evaluate_node(child, profile) for child in node["sub_criteria"]]
    return _rollup(child_results, node.get("rule", "all"))


def evaluate_criteria(stage, profile):
    results = []
    for node in get_stage_criteria(stage):
        results.append({
            "criterion": node["criterion"],
            "value":     _evaluate_node(node, profile),
            "rule":      node.get("rule"),
            "domain":    node.get("domain"),
        })
    return results


def stage_classification(profile):
    assigned_stage = "IDEATION"
    evidence = {}
    stopped_at = None

    for stage in STAGE_ORDER[1:]:
        stage_result = evaluate_criteria(stage, profile)
        evidence[stage] = stage_result

        if stage_result and all(item["value"] is True for item in stage_result):
            assigned_stage = stage
        else:
            stopped_at = stage
            break

    return {
        "assigned_stage": assigned_stage,
        "evidence":       evidence,
        "stopped_at":     stopped_at,
    }


def extract_failed_criteria(evidence):
    failed = []
    for stage, criteria in evidence.items():
        for item in criteria:
            if item["value"] is not True:
                failed.append({
                    "criterion": item["criterion"],
                    "value":     item["value"],   # False = confirmed gap | None = data missing
                    "stage":     stage,
                    "domain":    item.get("domain"),
                })
    return failed


def identify_blockers(failed_criteria):
    # Group by domain
    groups = {domain: [] for domain in BLOCKER_DOMAINS}
    for item in failed_criteria:
        domain = item.get("domain")
        if domain in groups:
            groups[domain].append(item)

    # Rank active domains by: earliest stage first, then count, then severity
    # False (confirmed gap) = severity 2 | None (data missing) = severity 1
    def _rank_key(domain):
        items = groups[domain]
        earliest = min((get_stage_index(i["stage"]) or 99) for i in items)
        count    = len(items)
        severity = sum(2 if i["value"] is False else 1 for i in items)
        return (earliest, -count, -severity)

    ranked_domains = sorted(
        [d for d in BLOCKER_DOMAINS if groups[d]],
        key=_rank_key,
    )

    return {
        "by_domain":      groups,
        "ranked_domains": ranked_domains,
        "total":          len(failed_criteria),
    }


def compute_confidence(evidence):
    total      = 0
    none_count = 0

    for criteria in evidence.values():
        for item in criteria:
            total += 1
            if item["value"] is None:
                none_count += 1

    if total == 0:
        return {"level": "low", "score": 0.0, "none_count": 0, "total_evaluated": 0}

    score = (total - none_count) / total

    if score >= 0.8:
        level = "high"
    elif score >= 0.5:
        level = "medium"
    else:
        level = "low"

    return {
        "level":           level,
        "score":           round(score, 4),
        "none_count":      none_count,
        "total_evaluated": total,
    }


def detect_perception_gap(profile, assigned_stage):
    self_assessed = _get_profile_value(profile, "self_assessed_stage")

    # diagnosed_stage is a stage name → convert to 1-based number
    diagnosed_number = (get_stage_index(assigned_stage) or 0) + 1

    # self_assessed_stage may be stored as int (1–6) or stage name string
    if isinstance(self_assessed, int):
        self_number = self_assessed
    elif isinstance(self_assessed, str):
        idx = get_stage_index(self_assessed)
        self_number = None if idx is None else idx + 1
    else:
        self_number = None

    if self_number is None:
        return {
            "self_assessed_stage": self_assessed,
            "diagnosed_stage":     assigned_stage,
            "gap_size":            None,
            "divergence":          None,
            "gap_direction":       None,
        }

    gap = self_number - diagnosed_number

    return {
        "self_assessed_stage": self_number,
        "diagnosed_stage":     diagnosed_number,
        "gap_size":            abs(gap),
        "divergence":          gap != 0,
        "gap_direction":       "overestimate" if gap > 0 else "underestimate" if gap < 0 else "aligned",
    }


def save_diagnostic_log(profile, metadata):
    return ProfileLog.objects.create(
        project=profile,
        author="diagnostic_engine",
        metadata=metadata,
    )


def diagnose_project(profile):
    # 1 — classify
    classification = stage_classification(profile)
    assigned_stage = classification["assigned_stage"]
    evidence       = classification["evidence"]

    # 2 — extract failures and build blocker profile
    failed   = extract_failed_criteria(evidence)
    blockers = identify_blockers(failed)

    # 3 — confidence
    confidence = compute_confidence(evidence)

    # 4 — perception gap
    gap = detect_perception_gap(profile, assigned_stage)

    # 5 — assemble and persist
    assigned_stage_index = (get_stage_index(assigned_stage) or 0) + 1
    metadata = {
        "assigned_stage":       assigned_stage,
        "assigned_stage_index": assigned_stage_index,
        "stopped_at":           classification["stopped_at"],
        "evidence":             evidence,
        "failed_criteria":      failed,
        "blockers":             blockers,
        "confidence":           confidence,
        "perception_gap":       gap,
        "diagnosed_at":         datetime.now(timezone.utc).isoformat(),
    }

    profile.current_stage = assigned_stage_index
    profile.save(update_fields=["current_stage"])
    log = save_diagnostic_log(profile, metadata)

    return {
        "author":   "diagnostic_engine",
        "log_id":   log.id,
        "metadata": metadata,
    }
