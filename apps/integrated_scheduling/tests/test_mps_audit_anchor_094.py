import hashlib, json
from apps.integrated_scheduling.mps_decision_anchor import _receipt_hash

def test_receipt_hash_is_canonical():
    a={'b':2,'a':1}; b={'a':1,'b':2}
    assert _receipt_hash(a)==_receipt_hash(b)
    assert len(_receipt_hash(a))==64
