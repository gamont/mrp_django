from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.common.models import Plant


class OperationalUiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="planner", password="secret123")
        self.plant = Plant.objects.create(code="SP01", name="São Paulo")

    def test_login_required(self):
        response = self.client.get(reverse("ui:planner"))
        self.assertEqual(response.status_code, 302)

    def test_planner_page_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("ui:planner"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Planejamento MRP")

    def test_select_plant(self):
        other = Plant.objects.create(code="MG01", name="Minas Gerais")
        self.client.force_login(self.user)
        response = self.client.post(reverse("ui:select-plant"), {"plant_id": other.pk, "next": reverse("ui:planner")})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["ui_plant_id"], other.pk)

    def test_htmx_returns_partial(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("ui:planner"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<!doctype html>")
