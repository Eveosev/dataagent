"""Ordered typed roles define fact identity; provenance assertions remain distinct."""
from .identity import canonical,digest


def relation_key(scope,relation,roles):
    return 'fact:'+digest([scope,relation,[[r.role,r.value_type,canonical(r.value)] for r in roles]])
