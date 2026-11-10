"""Build catalog URLs from an observed filter reference without network calls."""
from __future__ import annotations

from urllib.parse import urlencode, urlsplit, urlunsplit

from .catalog import normalize_url


_OFF = {'', '0', '-'}


def parse_assignments(assignments: list[str]) -> dict[str, list[str]]:
    """Parse repeated CLI key=value assignments, preserving literal text values."""
    selected: dict[str, list[str]] = {}
    for assignment in assignments:
        if '=' not in assignment:
            raise ValueError('Each --set must have the form parameter=value')
        key, value = assignment.split('=', 1)
        key = key.strip()
        if not key:
            raise ValueError('Empty filter parameter')
        selected.setdefault(key, []).append(value.strip())
    return selected


def build_url(reference: dict, selections: dict, base_url: str | None = None) -> str:
    """Validate IDs/cardinality against captured controls and encode one URL.

    This proves consistency with the reference only. The caller must inspect the
    actual response before treating the generated selections as applied by B17.
    Wizard-only choices are not enabled until the crawl verifier can confirm them.
    City-specific location IDs cannot be moved to a different catalog context.
    """
    if not isinstance(reference, dict) or reference.get('schema_version') != 1:
        raise ValueError('Expected a version 1 filter reference JSON object')
    source = reference.get('source', {})
    if not isinstance(source, dict):
        raise ValueError('Filter reference source must be an object')
    source_url = source.get('url') or source.get('source_url')
    if not isinstance(source_url, str) or not source_url:
        raise ValueError('Filter reference has no source URL')
    original = urlsplit(normalize_url(source_url))
    base = urlsplit(normalize_url(base_url or source_url))
    if base.path != original.path:
        raise ValueError('Reference belongs to another catalog; export filters for the target city/format first')
    if not base.path.startswith(('/psiholog/', '/online/')):
        raise ValueError('Reference must describe a psychologist catalog')
    filters = reference.get('filters', {})
    if not isinstance(filters, dict):
        raise ValueError('Filter reference filters must be an object')
    if not isinstance(selections, dict):
        raise ValueError('Selections must be a mapping of query parameters to values')
    query, normalized = [], {}
    for key, raw in selections.items():
        if key not in filters:
            raise ValueError(f'Unknown filter {key!r}; use a query parameter from the filter reference')
        metadata = filters[key]
        if not isinstance(metadata, dict):
            raise ValueError(f'Invalid metadata for filter {key!r}')
        values = raw if isinstance(raw, list) else [raw]
        if any(not isinstance(value, (str, int)) or isinstance(value, bool) for value in values):
            raise ValueError(f'Filter {key!r} requires string or numeric option values')
        if metadata.get('kind') == 'text':
            values = list(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))
        else:
            values = list(dict.fromkeys(v.strip() for raw_value in values
                                        for v in str(raw_value).split(',') if v.strip()))
        if not values:
            continue
        multiple = metadata.get('multiple', metadata.get('kind') == 'multi_enum')
        if not multiple and len(values) > 1:
            raise ValueError(f'Filter {key!r} accepts only one value')
        if metadata.get('crawl_compatible') is False:
            raise ValueError(f'Filter {key!r} is exposed by the site but unsupported by crawl')
        if metadata.get('kind') == 'text':
            minimum = metadata.get('min_length', metadata.get('minlength', 0)) or 0
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
                raise ValueError(f'Invalid minimum length for filter {key!r}')
            if len(values[0]) < minimum:
                raise ValueError(f'Filter {key!r} requires at least {minimum} characters')
        else:
            options = metadata.get('options', [])
            if not isinstance(options, list) or any(not isinstance(option, dict) or 'value' not in option for option in options):
                raise ValueError(f'Invalid option list for filter {key!r}')
            allowed = {str(option['value']) for option in options}
            invalid = set(values) - allowed
            if invalid:
                raise ValueError(f'Unsupported value(s) for {key!r}: {sorted(invalid)}; no automatic threshold rounding')
            forbidden = {str(v) for v in metadata.get('unsupported_crawl_values', [])}
            if key == 'byfoto':
                forbidden.add('1')
            if set(values) & forbidden:
                raise ValueError(f'Value for {key!r} requires a view unsupported by crawl')
            if set(values) & _OFF and len(values) > 1:
                raise ValueError(f'Cannot combine unset and active values for {key!r}')
            values = [v for v in values if v not in _OFF]
        if values:
            normalized[key] = values
            query.append((key, values[0] if not multiple else ','.join(values)))
    if 'price1' in normalized and 'price2' in normalized:
        try:
            lower, upper = int(normalized['price1'][0]), int(normalized['price2'][0])
        except ValueError as exc:
            raise ValueError('Price thresholds must be numeric') from exc
        if lower > upper:
            raise ValueError('Minimum price must not exceed maximum price')
    return urlunsplit(base._replace(query=urlencode(query), fragment=''))
