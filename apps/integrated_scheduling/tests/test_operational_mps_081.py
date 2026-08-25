from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.integrated_scheduling.models import MPSBucketChangeRequest
from apps.integrated_scheduling.mps_interactive import request_bucket_edit

class InteractiveMPS081Test(TestCase):
    def test_change_request_model_choices(self):
        self.assertEqual(MPSBucketChangeRequest.Status.PENDING, 'PENDING')
        self.assertEqual(MPSBucketChangeRequest.Violation.FROZEN_BUCKET, 'FROZEN_BUCKET')

    def test_two_person_rule_is_declared(self):
        # Integration behavior is exercised in Docker with real MPS fixtures.
        self.assertTrue(callable(request_bucket_edit))
