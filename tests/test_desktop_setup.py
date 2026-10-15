import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from app.api.views.user import onboarding_save
from app.cultures.desktop import culturas_da_instalacao
from app.models import Cultura
from app.views.desktop_setup import desktop_setup


class DesktopSetupTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.override = override_settings(AMPLIAGRO_DESKTOP_DATA_DIR=self.root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.env = patch.dict(
            "os.environ",
            {
                "AMPLIAGRO_SETUP_TOKEN": "test-token",
                "AMPLIAGRO_TERMS_HASH": "terms-v1",
                "AMPLIAGRO_WEB_URL": "",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.culture = Cultura.objects.create(nome="Café de teste", grupo="graos")
        self.other = Cultura.objects.create(nome="Outra cultura", grupo="graos")
        self.factory = RequestFactory()

    def post(self, **changes):
        body = {
            "mode": "local",
            "culturas": [self.culture.pk],
            "accepted": True,
            "termsHash": "terms-v1",
        }
        body.update(changes)
        request = self.factory.post(
            "/desktop/setup/",
            json.dumps(body),
            content_type="application/json",
            HTTP_X_AMPLIAGRO_SETUP="test-token",
        )
        return desktop_setup(request)

    def test_requires_private_process_token(self):
        self.assertEqual(
            desktop_setup(self.factory.get("/desktop/setup/")).status_code, 404
        )

    def test_web_server_cannot_use_local_setup(self):
        with override_settings(AMPLIAGRO_DESKTOP_DATA_DIR=None):
            self.assertEqual(self.post().status_code, 404)

    def test_terms_and_available_mode_are_required(self):
        for payload in (
            {"accepted": False},
            {"termsHash": "old"},
            {"mode": "cloud"},
            {"culturas": []},
            {"culturas": [True]},
            {"culturas": [999999]},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.post(**payload).status_code, 400)
        self.assertFalse((self.root / "installation.json").exists())

    def test_only_selected_profiles_are_prepared_and_used_by_onboarding(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(
            [p.name for p in (self.root / "culturas").iterdir()],
            [f"{self.culture.pk}.json"],
        )
        config = json.loads(
            (self.root / "installation.json").read_text(encoding="utf-8")
        )
        self.assertTrue(config["acceptedAt"])
        self.assertEqual(config["termsHash"], "terms-v1")
        self.assertEqual(culturas_da_instalacao(), [self.culture.pk])
        self.assertTrue(Cultura.objects.filter(pk=self.other.pk).exists())

    def test_failed_profile_write_does_not_mark_installation_complete(self):
        with patch(
            "app.views.desktop_setup._gravar_atomico", side_effect=OSError("disk full")
        ), self.assertRaises(OSError):
            self.post()
        self.assertFalse((self.root / "installation.json").exists())

    def test_signup_uses_installation_selection_instead_of_asking_again(self):
        self.post()
        user = User.objects.create_user(username="desktop-grower")
        request = APIRequestFactory().post(
            "/api/onboarding/save/",
            {"nome_fazenda": "Minha fazenda", "area": 12, "culturas": [self.other.pk]},
            format="json",
        )
        force_authenticate(request, user=user)
        response = onboarding_save(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(user.propriedades.get().culturas.values_list("pk", flat=True)),
            [self.culture.pk],
        )
