"""Role policy for local development; unknown roles fail closed."""
ROLES = frozenset({'ADMIN', 'SALES', 'BOD'})

def normalize_role(value):
    return value.strip().upper() if isinstance(value, str) else ''

def allowed_role(value):
    return normalize_role(value) in ROLES

def can_access_etl(value):
    return normalize_role(value) == 'ADMIN'

def local_development(debug, remote_addr):
    return bool(debug) and remote_addr in {'127.0.0.1', '::1'}
