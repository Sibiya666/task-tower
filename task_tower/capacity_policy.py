"""Pure count/resource policy schemas; no measurement or execution authority."""
import re


class UnsupportedCapacityMode(ValueError):
    pass


def require_legacy_capacity(config, *, executor_config=None):
    """New policy loading must not fall through to fixed-count legacy claims."""
    executor = executor_config if executor_config is not None else config.get('_executor_config', {})
    if config.get('version', 1) == 2 or executor.get('version', 1) == 2:
        raise UnsupportedCapacityMode('group_runtime_unavailable')


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate capacity policy JSON key')
        result[key] = value
    return result


def positive(value):
    if type(value) is not int or not 1 <= value <= 2**63 - 1:
        raise ValueError('Invalid capacity integer')
    return value


def counts(value):
    if not isinstance(value, dict) or set(value) != {'max_executors', 'max_inflight'}:
        raise ValueError('Invalid capacity counts')
    return {key: None if item is None else positive(item) for key, item in value.items()}


def harness_resources(value, profiles):
    if not isinstance(value, dict) or not value:
        raise ValueError('Missing harness resource grants')
    normalized, aliases = {}, {}
    for name, grant in value.items():
        if name not in profiles or not isinstance(grant, dict) or set(grant) != {'pool_id','cpu_millis','memory_bytes','max_parallel'}:
            raise ValueError('Invalid harness resource grant')
        pool = grant['pool_id']
        if not isinstance(pool, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', pool):
            raise ValueError('Invalid harness pool')
        authority = tuple(profiles[name]['argv'])
        if authority in aliases and aliases[authority] != pool:
            raise ValueError('Harness alias splits pool')
        aliases[authority] = pool
        normalized[name] = dict(pool_id=pool, cpu_millis=positive(grant['cpu_millis']),
            memory_bytes=positive(grant['memory_bytes']),
            max_parallel=None if grant['max_parallel'] is None else positive(grant['max_parallel']))
    return normalized
