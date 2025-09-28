from typing import List, Dict, Any


def normalize_results(raw_results: Any) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []

    if not raw_results:
        return normalized

    for entry in raw_results:
        if hasattr(entry, 'to_dict'):
            normalized.append({
                'source': entry.__class__.__name__,
                'content': str(entry.to_dict())
            })
        elif hasattr(entry, 'to_string'):
            normalized.append({
                'source': entry.__class__.__name__,
                'content': entry.to_string()
            })
        elif isinstance(entry, dict):
            normalized.append({
                'source': entry.get('source', 'Result'),
                'content': str({k: v for k, v in entry.items() if k != 'source'})
            })
        else:
            normalized.append({
                'source': getattr(entry, '__class__', type('Result', (), {})).__name__,
                'content': str(entry)
            })
    return normalized


def execute_biomedical_query(query_text: str) -> Dict[str, Any]:
    try:
        from main import DBFinder
    except Exception as exc:
        return {
            'classification': 'unavailable',
            'results': [],
            'error': f'Query router unavailable: {exc}'
        }

    finder = DBFinder()
    try:
        raw_results = finder.route_and_query(query_text)
    except Exception as exc:
        return {
            'classification': 'error',
            'results': [],
            'error': str(exc)
        }

    classification = getattr(finder, 'last_classification', '') or 'unknown'

    if raw_results is None:
        return {
            'classification': classification,
            'results': [],
            'error': 'No results returned for the supplied query.'
        }

    return {
        'classification': classification,
        'results': normalize_results(raw_results),
        'error': None
    }
