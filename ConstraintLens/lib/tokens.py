# lib/tokens.py — entityToken <-> object resolution (SPEC.md section 4).

import adsk.fusion


def token_of(entity) -> str | None:
    try:
        return entity.entityToken
    except Exception:
        return None


def resolve(design: adsk.fusion.Design, token: str):
    """Return the first entity matching the token, or None."""
    if not token:
        return None
    try:
        results = design.findEntityByToken(token)
    except Exception:
        return None
    if not results:
        return None
    return results[0]
