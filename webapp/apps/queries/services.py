import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings


def _extract_link(candidate: Dict[str, Any]) -> Optional[str]:
    for key in ("url", "link", "trial_url", "target_url", "href"):
        value = candidate.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None


def _build_fields(candidate: Dict[str, Any]) -> List[Dict[str, str]]:
    fields: List[Dict[str, str]] = []
    field_map = {
        "phase": "Trial phase",
        "status": "Recruitment status",
        "condition": "Condition",
        "disease": "Disease",
        "evidence": "Evidence score",
        "evidence_score": "Evidence score",
        "score": "Score",
        "mechanism": "Mechanism",
        "target": "Target",
        "drug": "Drug",
    }

    for key, label in field_map.items():
        value = candidate.get(key)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value)
        fields.append({"label": label, "value": str(value)})
    return fields


def normalize_results(raw_results: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    if not raw_results:
        return normalized

    for entry in raw_results:
        if hasattr(entry, 'to_dict'):
            candidate = entry.to_dict()
            title = candidate.get('title') or candidate.get('name') or entry.__class__.__name__
            summary = candidate.get('summary') or candidate.get('description') or ""
            normalized.append({
                'source': candidate.get('source') or entry.__class__.__name__,
                'title': str(title),
                'summary': str(summary),
                'fields': _build_fields(candidate),
                'link': _extract_link(candidate),
                'raw': candidate,
            })
        elif hasattr(entry, 'to_string'):
            normalized.append({
                'source': entry.__class__.__name__,
                'title': getattr(entry, 'name', entry.__class__.__name__),
                'summary': entry.to_string(),
                'fields': [],
                'link': None,
                'raw': {},
            })
        elif isinstance(entry, dict):
            title = entry.get('title') or entry.get('name') or entry.get('id') or entry.get('source', 'Result')
            summary = entry.get('summary') or entry.get('description') or ''
            normalized.append({
                'source': entry.get('source', 'Result'),
                'title': str(title),
                'summary': str(summary or ''),
                'fields': _build_fields(entry),
                'link': _extract_link(entry),
                'raw': entry,
            })
        else:
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
