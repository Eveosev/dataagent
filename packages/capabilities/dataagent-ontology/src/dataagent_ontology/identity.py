"""Scope/type/key-tuple identity; missing keys never merge by display name."""
import hashlib
import json
from decimal import Decimal


def canonical(value):
    if isinstance(value,Decimal):
        sign,digits,exponent=value.as_tuple()
        digits=list(digits)
        while digits and digits[-1]==0:
            digits.pop();exponent+=1
        if not digits:return ['decimal',0,'0',0]
        return ['decimal',sign,''.join(map(str,digits)),exponent]
    if isinstance(value,bool):return ['boolean',value]
    if isinstance(value,int):return ['integer',str(value)]
    if isinstance(value,str):return ['string',value]
    if value is None:return ['null']
    raise ValueError('identity and relation values must be typed scalars')


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def entity_key(scope,entity_type,identity_strategy,keys):
    return 'entity:'+digest([scope,entity_type,identity_strategy,[[k,canonical(v)] for k,v in keys]])
