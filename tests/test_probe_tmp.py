from django.contrib.auth.models import User
from django.test import Client
from django.test.runner import DiscoverRunner
from django.test.utils import setup_test_environment, teardown_test_environment


def test_probe():
    pass


def _main():
    setup_test_environment()
    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = runner.setup_databases()
    try:
        u = User.objects.create_user(username="prod_probe", password="x1234567")
        PerfilUsuario = __import__(
            "app.models", fromlist=["PerfilUsuario"]
        ).PerfilUsuario
        print("perfil existe?", PerfilUsuario.objects.filter(user=u).exists())
        try:
            p = getattr(u, "perfil", None)
            print("getattr(user,'perfil',None) ->", repr(p))
        except Exception as exc:
            print("getattr LEVANTOU:", type(exc).__mro__[:4], exc)

        c = Client(raise_request_exception=False)
        c.force_login(u)
        for url in ("/api/estoque/", "/api/pecuaria/", "/api/maquinarios/"):
            r = c.get(url)
            print(url, "->", r.status_code, r.content[:120])
    finally:
        runner.teardown_databases(old_config)
        teardown_test_environment()


if __name__ == "__main__":
    _main()
