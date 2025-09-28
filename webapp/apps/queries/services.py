import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from django.conf import settings


try:  # pragma: no cover - pandas is optional at runtime
    import pandas as pd
except Exception:  # pragma: no cover - keep normalization resilient without pandas
    pd = None  # type: ignore


def _normalize_key(key: str) -> str:
    return ''.join(ch for ch in str(key).lower() if ch.isalnum())


def _flatten_dict(data: Dict[str, Any], parent_key: str = '') -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{parent_key}.{key}" if parent_key else str(key)
        if isinstance(value, dict):
            items.update(_flatten_dict(value, new_key))
        else:
            items[new_key] = value
    return items


FIELD_LABELS = {
    'phase': 'Trial phase',
    'phases': 'Trial phase',
    'maxphaseforindication': 'Max indication phase',
    'status': 'Recruitment status',
    'overallstatus': 'Recruitment status',
    'condition': 'Condition',
    'conditions': 'Condition',
    'disease': 'Disease',
    'diseasename': 'Disease',
    'diseaseid': 'Disease ID',
    'evidence': 'Evidence score',
    'evidencescore': 'Evidence score',
    'score': 'Score',
    'combinedscore': 'Combined score',
    'mechanism': 'Mechanism',
    'target': 'Target',
    'targetclass': 'Target class',
    'targetapprovedsymbol': 'Target symbol',
    'targetapprovedname': 'Target name',
    'drug': 'Drug',
    'drugname': 'Drug',
    'drugid': 'Drug ID',
    'nctnumber': 'NCT number',
    'interventions': 'Interventions',
}

LINK_KEYS = {_normalize_key(key) for key in ('url', 'link', 'trial_url', 'target_url', 'href')}


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)) and not value:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if pd is not None:
        try:
            # pandas treats NaN/NA values as "truthy" when compared directly
            if pd.isna(value):  # type: ignore[attr-defined]
                return False
        except TypeError:
            pass
    return True


def _extract_link(candidate: Dict[str, Any]) -> Optional[str]:
    if not isinstance(candidate, dict):
        return None
    for key, value in candidate.items():
        if isinstance(value, str) and value.startswith("http"):
            if _normalize_key(key) in LINK_KEYS:
                return value
    return None


def _build_fields(candidate: Dict[str, Any], skip_keys: Optional[Sequence[str]] = None) -> List[Dict[str, str]]:
    fields: List[Dict[str, str]] = []
    if not isinstance(candidate, dict):
        return fields

    skip = {_normalize_key(key) for key in (skip_keys or [])}
    seen_labels: set[str] = set()

    for key, value in candidate.items():
        normalized_key = _normalize_key(key)
        if normalized_key in skip or not _is_non_empty(value):
            continue
        label = FIELD_LABELS.get(normalized_key)
        if not label or label in seen_labels:
            continue
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(v) for v in value if v is not None)
        fields.append({"label": label, "value": str(value)})
        seen_labels.add(label)
    return fields


DEFAULT_TITLE_KEYS = (
    'title',
    'name',
    'label',
    'nct number',
    'drug.name',
    'target.approvedsymbol',
    'id',
)
DEFAULT_SUMMARY_KEYS = (
    'summary',
    'description',
    'status',
    'condition',
    'disease',
    'targetclass',
    'mechanism',
)


def _first_nonempty(candidate: Dict[str, Any], keys: Iterable[str]) -> Optional[Any]:
    targets = [_normalize_key(key) for key in keys]
    for target in targets:
        for actual_key, value in candidate.items():
            if _normalize_key(actual_key) == target and _is_non_empty(value):
                return value
    return None


def _normalize_mapping(
    candidate: Dict[str, Any],
    *,
    source: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = metadata or {}
    combined = dict(candidate)
    try:
        combined.update(_flatten_dict(candidate))
    except Exception:
        pass

    skip_fields: Sequence[str] = metadata.get('skip_fields', ())  # type: ignore[assignment]
    skip_fields = tuple(skip_fields) + ('title', 'name', 'summary', 'description', 'source', 'link', 'url', 'href')

    title_keys = metadata.get('title_field') or metadata.get('title_fields') or DEFAULT_TITLE_KEYS
    if isinstance(title_keys, str):
        title_keys = [title_keys]

    summary_keys = metadata.get('summary_field') or metadata.get('summary_fields') or DEFAULT_SUMMARY_KEYS
    if isinstance(summary_keys, str):
        summary_keys = [summary_keys]

    link_field = metadata.get('link_field') or metadata.get('link_fields')
    if isinstance(link_field, str):
        link_field = [link_field]

    title = _first_nonempty(combined, title_keys)
    summary = _first_nonempty(combined, summary_keys)
    link = _extract_link(combined)
    if not link and link_field:
        link_candidate = _first_nonempty(combined, link_field)
        if isinstance(link_candidate, str) and link_candidate.startswith('http'):
            link = link_candidate

    resolved_source = (
        candidate.get('source')
        if isinstance(candidate, dict) and candidate.get('source')
        else metadata.get('source')
        or source
        or 'Result'
    )

    fields = _build_fields(combined, skip_keys=skip_fields)

    return {
        'source': str(resolved_source),
        'title': str(title or resolved_source),
        'summary': str(summary or ''),
        'fields': fields,
        'link': link,
        'raw': candidate,
    }


def _iter_entries(raw: Any) -> Iterable[Any]:
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            yield from _iter_entries(item)
    else:
        yield raw


def normalize_results(raw_results: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    if not raw_results:
        return normalized

    for entry in _iter_entries(raw_results):
        if entry is None:
            continue

        if pd is not None and isinstance(entry, pd.DataFrame):
            metadata = getattr(entry, 'attrs', {}) or {}
            records = entry.to_dict(orient='records')
            for record in records:
                normalized.append(
                    _normalize_mapping(
                        record,
                        source=metadata.get('source') or entry.__class__.__name__,
                        metadata=metadata,
                    )
                )
            continue

        if pd is not None and isinstance(entry, pd.Series):
            metadata = getattr(entry, 'attrs', {}) or {}
            normalized.append(
                _normalize_mapping(
                    entry.to_dict(),
                    source=metadata.get('source') or entry.__class__.__name__,
                    metadata=metadata,
                )
            )
            continue

        if hasattr(entry, 'to_dict') and not isinstance(entry, dict):
            candidate = entry.to_dict()
            if isinstance(candidate, dict):
                normalized.append(
                    _normalize_mapping(
                        candidate,
                        source=entry.__class__.__name__,
                    )
                )
                continue

        if isinstance(entry, dict):
            normalized.append(_normalize_mapping(entry, source=entry.get('source')))
            continue

        normalized.append({
            'source': getattr(entry, '__class__', type('Result', (), {})).__name__,
            'title': getattr(entry, 'title', 'Result'),
            'summary': str(entry),
            'fields': [],
            'link': None,
            'raw': {},
        })

    return normalized


ProgressCallback = Callable[[int, str], None]


def execute_biomedical_query(query_text: str, progress_callback: Optional[ProgressCallback] = None) -> Dict[str, Any]:
    repo_root = Path(settings.BASE_DIR).resolve().parent
    base_dir = Path(settings.BASE_DIR).resolve()

    for candidate in (repo_root, base_dir):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)

    try:
        from main import DBFinder
    except Exception as exc:
        return {
            'classification': 'unavailable',
            'results': [],
            'error': f'Query router unavailable: {exc}'
        }

    finder = DBFinder()
    if progress_callback:
        try:
            progress_callback(15, 'Classifying query')
        except Exception:
            pass
    try:
        raw_results = finder.route_and_query(query_text, progress_callback=progress_callback)
    except Exception as exc:
        return {
            'classification': 'error',
            'results': [],
            'error': str(exc)
        }

    classification = getattr(finder, 'last_classification', '') or 'unknown'
    resolution = getattr(finder, 'last_resolution', classification)
    rationale = getattr(finder, 'last_rationale', '')

    if raw_results is None:
        return {
            'classification': classification,
            'resolution': resolution,
            'rationale': rationale,
            'results': [],
            'error': 'No results returned for the supplied query.'
        }

    return {
        'classification': classification,
        'resolution': resolution,
        'rationale': rationale,
        'results': normalize_results(raw_results),
        'error': None
    }
