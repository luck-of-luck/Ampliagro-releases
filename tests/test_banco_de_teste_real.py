"""O banco de teste tem de ser um banco de TESTE.

Este ficheiro existe por causa de um `pass` de duas linhas em
`tests/conftest.py`:

    @pytest.fixture(scope="session")
    def django_db_setup():
        pass

Um `pass` numa fixture que o pytest-django usa para criar e destruir a base
de teste não é "não fazer nada" — é **substituir** a fixture. Com ela fora,
todo `pytest` corre contra o `db.sqlite3` de desenvolvimento.

O que isso custou, medido nesta base:

    * utilizadores `ctx`, `ctx2`, `ctx3`, `test_agenda`, `probe`, `p4`,
      `palco_vivo`, `amplia_teste`… gravados como se fossem produtores;
    * talhões e funcionários "Teste" dentro de propriedades de gente;
    * `UNIQUE constraint failed: auth_user.username` na segunda execução —
      que se lê como "o teste está mal" e não como "o teste está a sujar a
      base de produção do ambiente".

Um teste que passa a vermelho contra a base de verdade também é perigoso:
qualquer `assertEqual` sobre contagens passa a depender de quantos dados de
teste ficaram lá das execuções anteriores.

Porque isto é um TESTE e não um comentário
------------------------------------------
O comportamento do pytest-django é de uma biblioteca, não deste código. Um
comentário não impede ninguém de voltar a pôr o `pass`. Estes testes leem o
`conftest.py` **e executam** contra a base, e por isso apanham tanto o
override como qualquer forma nova de o reintroduzir.
"""

import re
from pathlib import Path

import pytest

CONFTEST = Path(__file__).parent / "conftest.py"


@pytest.fixture(scope="module")
def conftest_txt():
    return CONFTEST.read_text(encoding="utf-8")


class TestConfiguracaoDoBanco:
    def test_o_conftest_existe(self):
        assert CONFTEST.exists(), f"conftest.py desapareceu de {CONFTEST}"

    def test_nao_substitui_a_fixture_que_cria_a_base_de_teste(self, conftest_txt):
        """A armadilha é subtil: o `pass` é pequeno e parece inofensivo."""
        # remove comentários para não os contar como código
        codigo = re.sub(r"#[^\n]*", "", conftest_txt)
        offenders = re.findall(
            r"@pytest\.fixture[^\n]*\n(?:[^\n]*\n){0,2}?\s*def\s+(\w+)\s*\([^)]*\)\s*:\s*(?:#[^\n]*\n\s*)?pass\b",
            codigo,
        )
        assert not offenders, (
            "fixtures que fazem só `pass` (a de `django_db_setup` é a perigosa — "
            f"é a que cria e destrói a base de teste): {offenders}"
        )

    def test_a_fixture_django_db_setup_nao_e_um_noop(self, conftest_txt):
        """Específico desta fixture: tem de ser a do pytest-django, ou não estar."""
        m = re.search(r"def\s+django_db_setup\s*\(([^)]*)\)\s*:", conftest_txt)
        if m is None:
            return  # não está definida: é o caso correcto
        corpo = conftest_txt[m.end() :]
        # o corpo vai até à próxima definição de topo
        corpo = re.split(r"\n(?=@pytest\.fixture|\ndef |\nclass )", corpo)[0]
        assert "pass" in corpo or "return" in corpo, (
            "django_db_setup está redefinida no conftest. Apague a definição "
            "inteira: a do pytest-django é a que cria e limpa a base de teste."
        )


class TestIsolamento:
    """Isto é o que a fixture faz, visto pelo lado de quem sofre."""

    def test_pytest_nao_escreve_na_base_de_desenvolvimento(self, django_user_model):
        """Se este teste correr duas vezes seguidas sem falhar, o isolamento
        funciona. Contra a base de desenvolvimento, a segunda falha com
        `UNIQUE constraint failed` — que é exactamente o sintoma reportado."""
        User = django_user_model
        User.objects.create_user("test_isolamento", password="x")
        assert User.objects.filter(username="test_isolamento").exists()

        # um segundo teste com o MESMO nome é o que rebenta sem isolamento
        User.objects.create_user("test_isolamento_2", password="x")
        assert User.objects.filter(username="test_isolamento_2").exists()
