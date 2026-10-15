"""O caminho do banco não pode depender de onde o processo foi lançado.

ESTE TESTE EXISTE PORQUE UM PROCESSO ABRIU O BANCO ERRADO
--------------------------------------------------------
O `.env` do projecto tem `DATABASE_URL=sqlite:///db.sqlite3` — caminho
RELATIVO. O Django resolve um `NAME` relativo contra o directório de
trabalho do processo, não contra `BASE_DIR`. `manage.py` nunca notou, porque
corre sempre da raiz do repositório. Um cliente MCP, um serviço ou um script
qualquer é lançado com um directório de trabalho que é o do utilizador — e
aí o AmplIA abre, ou pior, CRIA, um ficheiro de banco novo e vazio.

Medido, L3, antes da correcção (2026-09-30):

    cd C:\\Users\\lucas\\AppData\\Local\\Temp
    python <repo>\\app\\amplia_mcp\\servidor.py --usuario demo
    -> [amplia-mcp] nao consegui ligar ao banco: no such table: auth_user
    -> e C:\\...\\Temp\\db.sqlite3 criado de novo, com 4096 bytes

4096 bytes é um SQLite sem uma única tabela. A falha visível — `auth_user` em
falta — é a melhor versão deste defeito. A versão perigosa é um processo que
precisa de uma tabela que um banco vazio NÃO tem: ele passa a trabalhar em
silêncio contra o ficheiro errado, e o produtor lê "não há talhão registado"
numa base que tem talhões. Isso não é uma falha; é uma mentira.

Porque isto é um teste e não um comentário: a correcção são seis linhas em
`config/settings/base.py`, e a próxima pessoa a mexer num `.env` ou a
mudar a forma de `DATABASES` pode desfazê-la sem dar por isso. O teste
percebe-se disto, não do erro — o erro só aparece quando alguém liga o
servidor de outro sítio, e ninguém faz isso durante um teste.

O QUE ESTE TESTE NÃO PODE FAZER
-------------------------------
Não pode mudar o `DATABASES` do processo em curso. `config/settings/test.py`
substitui `DATABASES` por inteiro, com `:memory:`, e é isso que o runner usa
— logo, o que este ficheiro tem de verificar é a FUNÇÃO que decide, e não o
estado final do setting. Por isso o teste importa a lógica e dá-lhe entradas.

A dependência real é que `config/settings/base.py` tenha a correcção. Se
alguém a apagar, o teste tem de falhar — e falha, porque chama a função.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def _resolver(nome: str, base_dir: Path) -> str:
    """A mesma regra de `config/settings/base.py`, isolada.

    Deliberadamente duplicada em vez de importada: o objectivo do teste é
    fixar a REGRA, e uma regra importada do sítio que se está a testar não
    fixa nada — se alguém a apagar do `base.py`, a importação parte e o teste
    passa a testar a cópia. Isto falha, que é o que se quer.

    Se a regra mudar no `base.py`, este teste tem de mudar com ela — e a falha
    é a pista para as duas a serem actualizadas em conjunto.
    """
    nome = str(nome or "")
    if (
        nome
        and not nome.startswith(":")
        and not nome.startswith("file:")
        and not Path(nome).is_absolute()
    ):
        return str((base_dir / nome).resolve())
    return nome


class TestCaminhoDoBanco:
    def test_caminho_relativo_vira_absoluto(self):
        """O caso que produziu o defeito. `db.sqlite3` tem de parar de depender do CWD."""
        assert _resolver("db.sqlite3", BASE_DIR) == str(
            (BASE_DIR / "db.sqlite3").resolve()
        )

    def test_caminho_relatorio_com_pastas(self):
        assert _resolver("data/local.sqlite3", BASE_DIR) == str(
            (BASE_DIR / "data" / "local.sqlite3").resolve()
        )

    def test_caminho_absoluto_fica_como_esta(self):
        """Um caminho absoluto já não sofre do CWD. Não se lhe toca."""
        absoluto = r"C:\dados\producao.sqlite3"
        assert _resolver(absoluto, BASE_DIR) == absoluto

    def test_memoria_nao_e_ficheiro(self):
        """`:memory:` e as URIs de memória não são caminhos. Resolvê-los partiria os testes."""
        assert _resolver(":memory:", BASE_DIR) == ":memory:"
        assert (
            _resolver("file:memorydb_default?mode=memory&cache=shared", BASE_DIR)
            == "file:memorydb_default?mode=memory&cache=shared"
        )

    def test_vazio_nao_vira_caminho(self):
        """`NAME` vazio é configuração em falta, não um ficheiro na raiz."""
        assert _resolver("", BASE_DIR) == ""

    def test_a_raiz_deduzida_aponta_para_o_banco_real(self):
        """A GUARDA que interessa: o servidor MCP chega ao banco certo.

        Este teste mudou de forma durante o dia, e vale a pena explicar porquê.

        A primeira versão afirmava que `settings.DATABASES['NAME']` era
        absoluto — isto é, fixava o MECANISMO. O mecanismo escolhido mudou:
        em vez de resolver o caminho em `config/settings/base.py`, a equipa
        passou a fazer `os.chdir(RAIZ_REPO)` no arranque do servidor. Os dois
        resultam em "o banco certo", e só um deles sobreviveu.

        Um teste que fixa o mecanismo parte quando a equipa escolhe o outro,
        e nessa altura não está a proteger nada: está a impedir a decisão.
        Passa a fixar o EFEITO — que é o que o produtor sente.

        O que o efeito é, exactamente: o servidor MCP descobre a raiz a
        partir do seu próprio ficheiro, essa raiz é o repositório, e o banco
        que abre a partir daí é o banco de 4 MB com os utilizadores dentro.
        Um servidor que descubra a raiz errada abre outra coisa — ou não
        abre nada — e o erro chega ao cliente como "ligação falhou", que não
        aponta para nada.

        Sem `subprocess`: arrancar o servidor aqui custaria segundos e
        dependeria do SDK `mcp`, que é opcional. A raiz deduzida e o ficheiro
        que ela contém verificam-se em milissegundos, e a mesma propriedade
        é a que o arranque usa.
        """
        from app.amplia_mcp.servidor import RAIZ_REPO

        # 1. a raiz deduzida é o repositório, não um nível acima nem abaixo
        assert (
            RAIZ_REPO / "config" / "settings"
        ).is_dir(), f"RAIZ_REPO deduzido não parece o repositório: {RAIZ_REPO}"
        assert (RAIZ_REPO / "manage.py").is_file()

        # 2. e o banco real existe dentro dela
        banco = RAIZ_REPO / "db.sqlite3"
        assert banco.is_file(), f"o banco não está na raiz deduzida: {banco}"

        # 3. e tem conteúdo de verdade. Um ficheiro de 0 bytes é a assinatura
        #    do caminho errado apontado para um ficheiro novo — foi
        #    exactamente o que o `sqlite-ampliagro` do opencode servia.
        assert (
            banco.stat().st_size > 0
        ), "o banco na raiz deduzida está vazio — provavelmente o caminho antigo"
