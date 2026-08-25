import hashlib, json
from django.test import TestCase
from apps.integrated_scheduling.mps_decision_audit import GENESIS, _event_hash
class AuditHashContract093Tests(TestCase):
    def test_hash_is_deterministic_and_chained(self):
        from django.utils import timezone
        t=timezone.now(); p={'candidate_id':7,'x':'á'}
        a=_event_hash(1,1,'CANDIDATE_SELECTED',t,'alice',p,GENESIS)
        b=_event_hash(1,1,'CANDIDATE_SELECTED',t,'alice',p,GENESIS)
        self.assertEqual(a,b); self.assertEqual(len(a),64)
        c=_event_hash(1,2,'SUBMITTED',t,'alice',{},a)
        self.assertNotEqual(a,c)
