from django.test import TestCase
from apps.integrated_scheduling.models import MPSMajorIncident, MPSMajorIncidentPostmortem, MPSMajorIncidentAction

class IncidentCommand099ContractTests(TestCase):
    def test_major_incident_statuses(self):
        values={x for x,_ in MPSMajorIncident.Status.choices}
        self.assertTrue({'DETECTED','ACTIVE','MONITORING','RESOLVED','CLOSED'} <= values)

    def test_postmortem_approval_status_exists(self):
        values={x for x,_ in MPSMajorIncidentPostmortem.Status.choices}
        self.assertIn('APPROVED', values)

    def test_capa_action_types(self):
        values={x for x,_ in MPSMajorIncidentAction.ActionType.choices}
        self.assertEqual(values, {'CONTAINMENT','CORRECTIVE','PREVENTIVE'})
