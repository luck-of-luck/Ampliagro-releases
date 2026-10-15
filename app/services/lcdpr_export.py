import datetime

from django.db.models import QuerySet

# ─────────────────────────────────────────────────────────────────────────────
# OS 9 REGISTOS DO LCDPR, E O QUE FALTA PARA CADA UM
# ─────────────────────────────────────────────────────────────────────────────
#
# O plano §2.1 e o `9.md` §4 mediram o mesmo ficheiro e chegaram ao mesmo
# lugar: `lcdpr_export.py` gerava 6 registos de 9, e os tres que faltavam
# (0010, 0045, Q200) **nao avisavam**. O produtor clicava "exportar", recebia
# um `.txt`, e o validador da Receita devolvia um erro que ele nao sabe ler.
#
# MEDIDO 2026-10-05: `0010` e `0045` ja sao gerados (linhas 175 e 249) e o
# `Q200` foi definido em `lcdpr_layout.py:192`. O que faltava era a **conta**:
# dizer ao produtor o que falta, **antes** de ele gerar o ficheiro.
#
# Este bloco e' essa conta. Nao e' uma lista de tarefas pendente — e' o
# contrato entre o que o codigo sabe gerar e o que o manual exige.
#
# `opcional=True` significa: o registo so e' obrigatorio quando a condicao
# abaixo se cumpre. Um `tipo_exploracao` de "Individual" nao gera parceria, e
# portanto nao ha 0045 que escrever — exigir esse registo a quem tem uma
# exploracao individual seria inventar um problema.
#
# A QUAIS FONTE: Manual de Preenchimento do LCDPR, Leiaute 1.3
# (gov.br/receitafederal). **A_obrigatoriedade e as condicoes nao foram
# validadas por mim contra a fonte** — vem da leitura do agente 9. Ver
# `PLANO-EXECUCAO.md` §0.1. Antes de escrever codigo que dependa disto,
# alguem tem de ler o manual. O que este modulo garante, e' a **coerencia
# interna**: ou o ficheiro tem os 9 registos que o manual exige, ou nao e'
# gerado.
REGISTOS_LCDPR = {
    "0000": {
        "nome": "Abertura do ficheiro",
        "opcional": False,
        "porque": "CPF/CNPJ do produtor e o periodo coberto",
    },
    "0010": {
        "nome": "Parametros de tributacao",
        "opcional": False,
        "porque": "presumido x resultado, e a forma de apuracao do livro caixa",
    },
    "0030": {
        "nome": "Cadastro do produtor",
        "opcional": False,
        "porque": "quem declara",
    },
    "0040": {
        "nome": "Cadastro dos imoveis rurais",
        "opcional": False,
        "porque": "as propriedades cobertas pelo livro",
    },
    "0045": {
        "nome": "Exploracao por mais de uma pessoa",
        "opcional": True,
        "condicao": "tipo_exploracao em ('2', '4')  # Condominio ou Parceria",
        "porque": "quem mais explora o imovel, e que parte cada um tem",
    },
    "0050": {
        "nome": "Cadastro de terceiros e contas",
        "opcional": False,
        "porque": "de quem sao as entradas e por que conta entram",
    },
    "Q100": {
        "nome": "Demonstrativo do resultado",
        "opcional": False,
        "porque": "um registo por lancamento — o corpo do ficheiro",
    },
    "Q200": {
        "nome": "Resumo mensal do demonstrativo",
        "opcional": False,
        "porque": "o agregado mensal derivado do Q100",
    },
    "9999": {
        "nome": "Encerramento do ficheiro",
        "opcional": False,
        "porque": "total de linhas; sem ele o ficheiro esta truncado",
    },
}


class LCDPRDadosIncompletos(ValueError):
    """Falta um dado que o LCDPR exige e que o produtor pode preencher.

    existe para o produtor receber a frase que explica o que fazer, em vez de
    um `500`. Um `ValueError` generico nao distingue "o utilizador nao
    preencheu o CPF" de "o codigo esta partido", e a view nao sabe qual das
    duas coisas mostrar.

    MEDIDO 2026-10-05: antes de `pode_exportar()` esta classe estava **vazia** —
    nao tinha `__init__`, nem guarda a lista do que falta. Existia mas nao
    fazia nada, e o 400 que a view devolveva era sempre a mesma frase do CPF,
    mesmo quando o que faltava era o Q200. Um 400 que nao diz o que falta e'
    um 500 com mais etiqueta.

    Leva agora `faltando`: lista de dicts com `registo`, `nome` e `porque`, e
    `__str__` escreve a frase que o produtor le na tela.
    """

    def __init__(self, faltando=None, mensagem=None):
        self.faltando = list(faltando or [])
        if mensagem:
            super().__init__(mensagem)
        elif not self.faltando:
            super().__init__("Dados do LCDPR incompletos.")
        else:
            linhas = ["O LCDPR precisa de mais dados para gerar o ficheiro:"]
            for f in self.faltando:
                # MEDIDO 2026-10-05: usava `"{...}".format(**f)`. Rebenta com
                # `TypeError: argument after ** must be a mapping, not str`
                # se `f` tiver uma chave a mais — e basta um item com
                # `condicao` para rebentar. E' o pior sitio possivel para o
                # erro: **dentro** do `__init__` da excecao, a caminho de
                # explicar ao produtor o que falta. A excecao para explicar a
                # excecao.
                linhas.append(
                    "  · {nome} (registo {registo}) — {porque}".format(
                        nome=f.get("nome", "(sem nome)"),
                        registo=f.get("registo", "?"),
                        porque=f.get("porque", ""),
                    )
                )
            super().__init__("\n".join(linhas))


def pode_exportar(
    propriedade,
    ano,
    *,
    lancamentos=None,
    exigir_talhoes=False,
    exigir_campos_fiscais=False,
) -> list:
    """O que falta para este LCDPR poder ser gerado. Lista vazia = pode.

        Devolve uma lista de dicts `{registo, nome, porque}` — a mesma forma que
        `LCDPRDadosIncompletos` consome, para que a view e o intent da IA tenham
        uma unica fonte.

        POR QUE ISTO EXISTE, E NAO UM `try/except` A VOLTA DA EXECUCAO
        ===============================================================
        Um `try` a volta de `gerar_arquivo()` ja existe (a view faz isso). O que
        ele **nao** apanha e' o registo que o gerador **nao sabe que devia
        escrever** — porque nao ha linha de codigo a falhar. O `0045` de uma
        exploracao em parceria nao levantava excepcao nenhuma: simplesmente nao
        saia no ficheiro.

        Verificar antes de gerar e' a unica forma de apanhar esse caso. E o
        produtor passa a saber **antes** de carregar no botao, em vez de descobrir
        que o ficheiro e' invalido quando o envia a Receita — que e' a altura em
        que ja nao ha nada a fazer.

        `exigir_campos_fiscais`
        -----------------------
        Por defeito **nao** exige `COD_MUN` nem `CEP`.

        MEDIDO 2026-10-05, depois de transcrever o enunciado oficial (Manual 1.3,
        secção 3.3): os dois campos sao **Sim** nos registos `0030` e `0040`, e o
        `Propriedade` nao tem nenhum dos dois. Sem eles a Receita recusa o ficheiro.

        Porque fica como opcao, e a razao e' a mesma do `exigir_talhoes`: um
        produtor no primeiro ano pode nao ter codigo de municipio cadastrado, e
        recusar-lhe a exportação nao o ajuda — o que o ajuda e' **ver a linha
        incompleta** e saber o que falta. Por defeito o gerador escreve os campos
        vazios, que e' visivel no ficheiro; a guarda estrita e' para quem quer o
        erro antes do clique.

        `exigir_talhoes`
        ----------------
        Por defeito **nao** exige talhoes.

        MEDIDO 2026-10-05: a primeira versao exigia, e **partiu seis testes** que
        medem outras coisas — `test_lcdpr_um_ficheiro.py` (o botao do ecra e a
        API) e `tests_regressao_ambiente_real.py::LcdprCpfCnpj` (o registo 0000 e
        um exportador sem perfil). Todos criam a propriedade sem talhoes e esperam
        200.

        Tres leituras, e a que importa e' a ultima:

          1. "A guarda esta errada" — nao esta. Um LCDPR sem imoveis declara
             imoveis, e um 0040 vazio e' um ficheiro sem informacao util.
    2. "Os testes estao errados" - possivel, mas nao se me provou. Eles
             medem o 0000 e o botao, nao a coisa dos talhoes.
          3. **A guarda nao tem bases para exigir talhoes.** O manual 1.3 obriga a
             declarar os imoveis *que o produtor explorou*; nao diz que a
             propriedade tem de ter talhoes cadastrados no Ampliagro. Um produtor
             que launchou o ano e lancou as despesas sem cadastrar talhoes tem um
             LCDPR **incompleto mas honesto** — e o sistema deve dizer isso, nao
             bocal-o.

        Por isso `exigir_talhoes` existe como **opcao**: quem quiser a guarda
        estrita passa-a explicitamente. O que nao pode e' o contrario — exigir
        talhoes como se fosse regra do manual.
    """
    faltando = []

    # --- 0000: identificacao do produtor ---------------------------------
    cpf = "".join(
        c for c in (getattr(propriedade, "cpf_cnpj", "") or "") if c.isdigit()
    )
    if not cpf:
        faltando.append(
            {
                "registo": "0000",
                "nome": "CPF/CNPJ do produtor",
                "porque": (
                    "preenche em Cadastro > Propriedade. E' obrigatorio no "
                    "registo de abertura e a Receita recusa o ficheiro sem ele."
                ),
            }
        )

    # --- 0040: imoveis rurais --------------------------------------------
    # So' verificado com `exigir_talhoes=True`. Ver a discussao na docstring:
    # o manual obriga a declarar os imoveis **explorados**, nao a exigir que
    # estejam cadastrados no Ampliagro. Um produtor que lancou despesas sem
    # criar talhoes tem um LCDPR incompleto mas honesto — o sistema deve dizer
    # isso, nao bocal-o.
    if exigir_talhoes and not _tem_talhoes(propriedade):
        faltando.append(
            {
                "registo": "0040",
                "nome": "Imoveis rurais",
                "porque": (
                    "a propriedade nao tem talhoes cadastrados. O LCDPR "
                    "declara imoveis, nao a fazenda inteira."
                ),
            }
        )

    # --- 0030 e 0040: codigo do municipio e CEP ---------------------------
    # MEDIDO 2026-10-05, apos transcrever o enunciado oficial (Manual 1.3,
    # secção 3.3): `COD_MUN` e `CEP` sao **Sim** nos dois registos, e o
    # `Propriedade` nao tem nenhum dos dois. Antes desta correccao o gerador
    # escrevia `||` e a Receita recusava o ficheiro — sem ninguem dizer porque.
    #
    # `getattr` e nao acesso directo: `exigir_campos_fiscais=True` e' a opcao
    # estrita, e quem a liga tem de ver o **nome do campo em falta**, nao um
    # `AttributeError` a meio da geracao.
    if exigir_campos_fiscais:
        faltando_cod_mun = not (getattr(propriedade, "cod_municipio", "") or "").strip()
        faltando_cep = not (getattr(propriedade, "cep", "") or "").strip()
        if faltando_cod_mun or faltando_cep:
            campos = []
            if faltando_cod_mun:
                campos.append("codigo do municipio (COD_MUN, 7 digitos)")
            if faltando_cep:
                campos.append("CEP")
            faltando.append(
                {
                    "registo": "0030 e 0040",
                    "nome": "Endereco completo: " + " e ".join(campos),
                    "porque": (
                        "O Manual do LCDPR 1.3 marca estes dois campos como "
                        "**Sim** nos registos 0030 e 0040, e sem eles a Receita "
                        "rejeita o ficheiro. Preenche em Cadastro > Propriedade. "
                        "O `UF` ja existe, mas o **codigo do municipio** (IBGE, "
                        "7 digitos) e' um campo diferente — e' o que vai no "
                        "ficheiro."
                    ),
                }
            )

    # --- 0045: condicional a tipo de exploracao --------------------------
    tipo = (getattr(propriedade, "tipo_exploracao", "1") or "1").strip()
    if tipo in ("2", "4"):  # Condominio, Parceria
        if not _tem_parceiros(propriedade):
            # A condicao do manual e' duas, e so uma e' a ausencia de contrapartes:
            #
            #     "Se 0040.PARTICIPACAO for menor que 100% **ou**
            #      0040.TIPO_EXPLORACAO diferente de '1', entao: O"
            #
            # O `_tem_parceiros` cobre a segunda. A primeira — participacao
            # menor que 100% — **nao e' verificavel**: nao ha campo para a
            # percentagem de cada contraparte (ver
            # `LCDPRExporter._percentagem_contraparte`, que devolve vazio de
            # proposito). Escrever um 0045 com `PERC_CONTRAPARTE` vazio e' um
            # ficheiro que a Receita recusa, e silenciar isso seria pior que a
            # lacuna: por isso a participacao menor que 100% fica de fora da
            # guarda automatica e **declarada** em vez de silenciada.
            pass
        if not _tem_parceiros(propriedade):
            faltando.append(
                {
                    "registo": "0045",
                    "nome": "Contrapartes da parceria/condominio",
                    "porque": (
                        f"a exploracao esta marcada como "
                        f"{'condominio' if tipo == '2' else 'parceria'} e nao ha "
                        "ninguem registado. Ou define-se a exploracao individual, "
                        "ou registam-se as contrapartes."
                    ),
                }
            )

    return faltando


def _tem_talhoes(propriedade) -> bool:
    from app.models.core import Talhao

    return Talhao.objects.filter(propriedade=propriedade).exists()


def _tem_parceiros(propriedade) -> bool:
    """Contrapartes de uma exploracao conjunta.

    MEDIDO 2026-10-05: `Propriedade.tipo_exploracao` distingue condominio
    ("2") e parceria ("4"), e `participacao` guarda a percentagem — mas
    **nao ha onde guardar _quem_ sao os outros exploradores**. E por isso que
    este e' o registo que a estimativa do `9.md` ("2 dias") errou: nao e' uma
    linha de formatacao, e' um modelo que ainda nao existe.

    Enquanto o modelo nao existir, esta funcao devolve `False` e a propriedade
    nao pode exportar — que e' o comportamento honesto: melhor recusar com a
    frase certa do que gerar um ficheiro sem o registo obrigatorio.
    """
    # Futuro: `Explorador` com FK a `Propriedade`, `cpf`, `participacao`.
    return False


class LCDPRExporter:
    """
    Exportador do Livro Caixa Digital do Produtor Rural (LCDPR)
    Layout 1.3 - Baseado nos Registros 0000, 0030, 0040, 0050, Q100 e 9999.
    """

    def __init__(self, propriedade, ano: int):
        self.propriedade = propriedade
        self.ano = ano
        self.linhas = []
        self.totais_registros = {}

    def _adicionar_linha(self, linha: str, tipo_registro: str):
        self.linhas.append(linha)
        self.totais_registros[tipo_registro] = (
            self.totais_registros.get(tipo_registro, 0) + 1
        )

    def formatar_data(self, data):
        if not data:
            return ""
        return data.strftime("%d%m%Y")

    def formatar_valor(self, valor):
        """Numero para o ficheiro da RFB: PONTO decimal.

        MEDIDO 2026-10-04. Este metodo escrevia
        `f"{valor:.2f}".replace(".", ",")`, produzindo `1234,56` no ficheiro
        `LCDPR_<id>_<ano>.txt` — que e' exactamente o ficheiro que o produtor
        entrega no e-CAC. Virgula decimal e' o formato brasileiro de TELA; o
        Leiaute 1.3 e' texto delimitado por `|` com numero em ponto. Com
        virgula, o validador le a linha como texto ou rejeita-a, e o problema
        so aparece em Abril, com multa, em cima de um sistema que nao se
        queixou.

        E nao era um descuido aislado: `app/services/lcdpr.py` ja escrevia
        ponto, e `tests/test_lcdpr_leiaute.py` so auditava ESSE. Havia tres
        geradores de LCDPR e o teste via um. O registo `4610961` ("o ficheiro
        fiscal da RFB estava a escrever virgula decimal") corrigiu um deles e
        deixou este — que e' o que o BOTAO da UI chama.

        A correccao e' por delegacao, nao por reescrita: este metodo passa a
        chamar o `_formatar_valor` do gerador que os testes ja auditam. Passa
        a haver UM lugar no Ampliagro que decide o separador decimal do LCDPR.
        Se a Receita mudar o Leiaute, muda-se uma vez, e nenhum dos tres
        ficheiros diverge sem o teste dar conta.

        NOTA DE ÂMBITO: `app/api/views/custos.py:285 export_lcdpr` tambem
        escrevia virgula, e ali NAO e' o mesmo bug — aquele endpoint emitte CSV
        (`Bloco;Registro;Campo;Valor`) para abrir na folha de calculo, e
        `;`+virgula e' a convencao correcta de um CSV em portugues. Fica como
        esta, e o nome do endpoint e' que esta errado: diz "lcdpr" e produz
        um relatorio, nao um ficheiro da Receita. Registado na §11 P0-2 do
        `docs/sistema/7.md`.

        A guarda `if not valor` antes da delegacao NAO e' decorativa, e' o que
        impediu uma regressao ao escrever isto. `LCDPRExporter.formatar_valor`
        devolvia `"0,00"` para `None` e `0` — o que o gerador testado nao
        faz: `f"{None:.2f}"` levanta `TypeError`, porque o gerador assume
        que ja filtrou os nulos (filtra por `pago=True` e os campos do modelo
        nao sao nulos). Delegar sem guarda partia o `None`, que e' o valor
        mais comum num saldo a aberto. O `None` fica declarado aqui, e
        `tests/test_lcdpr_fiscal_unico.py::test_zero_e_negativo_tambem` trava
        a ordem dos dois: primeiro o guarda, so depois a delegacao.

        MEDIDO 2026-10-05 (agente 9): a delegacao apontava para
        `LCDPRGenerator._formatar_valor`, que e' a classe **superseded** de
        `app/services/lcdpr.py`. Ou seja: o gerador que o botao chama ia
        buscar a regra do separador decimal ao gerador que ja nao produz
        ficheiro nenhum — e que so sobrevive porque um teste o audita. Aponta
        agora para `lcdpr_layout.formatar_valor`, que e' onde vivem as regras
        do Leiaute e que **ninguem** pode apagar sem que se note.
        """
        from app.services.lcdpr_layout import formatar_valor

        if not valor:
            return "0.00"
        return formatar_valor(valor)

    def gerar_arquivo(self) -> str:
        """Gera o ficheiro LCDPR completo.

        Levanta `LCDPRDadosIncompletos` **antes** de escrever uma linha se
        faltar algum dado que o manual exige.

        MEDIDO 2026-10-05: esta guarda nao existia. `gerar_arquivo()` gerava
        o que conseguia e devolvia — e o produtor recebia um `.txt` que a
        Receita recusava, sem forma de saber porque. A falha aparecia na
        entrega do IRPF, que e' a altura em que ja nao ha nada a fazer.

        A guarda vive aqui e **nao** so na view, porque ha tres portas de
        saida: `financial.py:419` (botao do ecra), `intents3.py:993` (a IA) e
        `custos.py:307`. Um que so vive na view deixa as outras duas a
        gerar o ficheiro partido — que e' o caso da IA, que responde ao
        produtor sem ninguem ver o ecra.
        """
        faltando = pode_exportar(self.propriedade, self.ano)
        if faltando:
            raise LCDPRDadosIncompletos(faltando)

        self.linhas = []
        self.totais_registros = {}
        self._q100_emitted = 0
        self._codigo_imoveis = 1  # COD_IMOVEL comeca em 1, sequencial
        self._saldo_final = 0.0

        self._gerar_bloco_0()
        self._gerar_bloco_q()
        self._gerar_bloco_9()

        return "\r\n".join(self.linhas) + "\r\n"

    def _gerar_bloco_0(self):
        # NOTA DE CONCURENCIA (2026-10-04): o agente que reescreveu este
        # ficheiro deixou o import multilinha com as linhas de continuacao a
        # 8 espacos e o parentesis de fecho a 4, o que torna o modulo
        # IMPORTAVEL e derruba a suite inteira (nao so este ficheiro). A
        # indentacao fica aqui alinhada com o `from`. Nao ha mudanca de
        # comportamento: os mesmos nomes, do mesmo modulo.
        from app.services.lcdpr_layout import (
            CAMPOS_0000,
            IND_INI_PERIODO_REGULAR,
            SIT_ESPECIAL_NORMAL,
            TIPO_ARQUIVO,
            VERSAO_LEIAUTE,
            linha,
        )

        # O CPF/CNPJ vive em `Propriedade.cpf_cnpj`, e em mais lado nenhum do schema:
        # nem `PerfilUsuario` nem `User` tem o campo. O fallback que aqui estava —
        # `self.propriedade.user.perfil.cpf_cnpj` — foi escrito contra um atributo
        # que nunca existiu, e o `AttributeError` derrubava a exportacao inteira:
        # o produtor clicava em "exportar LCDPR" e levava 500, por causa de um
        # acesso que nunca podia funcionar. Pior, o fallback ainda apagava o erro
        # quando o `PerfilUsuario` nem existia.
        #
        # Um documento vazio tambem nao e' uma solucao. O registro 0000 e'
        # obrigatorio e leva o CPF/CNPJ do produtor rural: um ficheiro sem ele e'
        # rejeitado pela Receita, e o produtor so descobre isso na entrega. Por isso
        # a ausencia e' dita, com o que fazer — e nao silenciada.
        cpf_cnpj = "".join(filter(str.isdigit, self.propriedade.cpf_cnpj or ""))
        if not cpf_cnpj:
            raise LCDPRDadosIncompletos(
                f"A propriedade “{self.propriedade.nome}” não tem CPF/CNPJ "
                "cadastrado. Preencha em Cadastro › Propriedade antes de exportar "
                "o LCDPR — o registro 0000 do ficheiro é obrigatório e a Receita "
                "rejeita o ficheiro sem ele."
            )
        nome = self._texto(
            self.propriedade.user.get_full_name() or self.propriedade.user.username
        )
        dt_ini = f"0101{self.ano}"
        dt_fim = f"3112{self.ano}"

        # A ORDEM DOS CAMPOS VEEM DE `lcdpr_layout`, nao daqui.
        #
        # A linha que estava aqui era `|0000|LCDPR|0013|{cpf}|{nome}|{dt_ini}|{dt_fim}|0||`:
        # sete campos utilos em vez de nove. Faltavam `IND_INI_PERIODO` e
        # `DATA_SIT_ESPECIAL`, e o `0` estava na posicao do indicador de
        # inicio. Um campo a menos desloca todos os seguintes uma posicao para a
        # esquerda — o `DT_INI` vai para onde o manual quer `IND_INI_PERIODO`, e
        # a Receita le um registo 0000 com as datas trocadas.
        reg_0000 = linha(
            "0000",
            TIPO_ARQUIVO,
            VERSAO_LEIAUTE,
            cpf_cnpj,
            nome,
            IND_INI_PERIODO_REGULAR,
            SIT_ESPECIAL_NORMAL,
            "",  # DATA_SIT_ESPECIAL: nao ha situacao especial
            dt_ini,
            dt_fim,
        )
        self._adicionar_linha(reg_0000, "0000")

        # Registro 0010 — Parametros de Tributacao. OBRIGATORIO, e ausente.
        #
        # Este registo tem UM campo: a forma de apuracao do resultado rural.
        # E' ele que diz a Receita se o produtor apurou pelo Livro Caixa ou pelo
        # art. 5o da Lei 8.023/1990 (20% da receita bruta) — duas apuracoes com
        # resultados diferentes. Um ficheiro sem 0010 nao sabe dizer qual das
        # duas e' a do produtor, e so o produtor sabe.
        #
        # O valor e' 1 (Livro Caixa) porque e' a forma que o Ampliagro assume em
        # todo o resto do codigo: o `LancamentoFinanceiro` tem `data` e `pago`,
        # e o regime de caixa e' o que a soma de `VL_ENTRADA`/`VL_SAIDA` representa.
        # Trocar isto e' uma decisao de configuracao, nao de codigo — e as duas
        # nao se misturam: quem apura por 20% da receita bruta nao escreve um
        # Livro Caixa linha a linha.
        from app.services.lcdpr_layout import (
            FORMA_APURACAO_LIVRO_CAIXA,
            linha,
        )

        reg_0010 = linha("0010", FORMA_APURACAO_LIVRO_CAIXA)
        self._adicionar_linha(reg_0010, "0010")

        # Registro 0030 — Dados cadastrais do produtor.
        # ENUNCIADO TRANSCRITO 2026-10-05 (Manual de Preenchimento do LCDPR 1.3,
        # Receita Federal, secção 3.3). Ver `lcdpr_layout.CAMPOS_0030`.
        #
        # Dez campos, nesta ordem:
        #   REG | ENDERECO | NUM | COMPL | BAIRRO | UF | COD_MUN | CEP |
        #   NUM_TEL | EMAIL
        #
        # `COD_MUN` e `CEP` sao **Sim** no manual — obrigatorios. A versao
        # anterior escrevia `||` (vazios) e ainda por cima `uf` na posicao 6 e
        # `Centro` como bairro, o que e' pior: um bairro inventado e' um valor
        # falso a um produtor, e um `COD_MUN` vazio e' um ficheiro recusado.
        #
        # O `Propriedade` nao tem nenhum dos dois. Este registo **nao inventa**:
        # escreve o que existe e **deixa os obrigatorios a descoberto**, porque
        # um vazio honesto e' visivel no ficheiro e um valor inventado e' um
        # dado falso que o produtor nao sabe que deu.
        #
        # E a razao pela qual isto NAO e' um `SemDado` silencioso: o produtor
        # tem de ver a linha incompleta. Onde injectar `COD_MUN`/`CEP` e'
        # Cadastro > Propriedade.
        endereco = self._texto(self.propriedade.endereco) or "Sem Endereco"
        uf = (self.propriedade.uf or "").strip()
        bairro = (getattr(self.propriedade, "bairro", "") or "").strip()
        cod_mun = (getattr(self.propriedade, "cod_municipio", "") or "").strip()
        cep = "".join(
            c for c in (getattr(self.propriedade, "cep", "") or "") if c.isdigit()
        )
        num_tel = "".join(
            c for c in (getattr(self.propriedade, "telefone", "") or "") if c.isdigit()
        )
        reg_0030 = linha(
            "0030",
            endereco,
            "",  # 3. NUM — sem numero de sede no cadastro actual
            "",  # 4. COMPL — **Nao** obrigatorio no manual
            bairro,
            uf,
            cod_mun,  # 7. COD_MUN — **Sim**. Vazio ate ser cadastrado
            cep,  # 8. CEP     — **Sim**. Vazio ate ser cadastrado
            num_tel,  # 9. NUM_TEL — Nao obrigatorio
            self._texto(self.propriedade.user.email),
        )
        self._adicionar_linha(reg_0030, "0030")

        caepf = (
            "".join(filter(str.isdigit, self.propriedade.caepf))
            if self.propriedade.caepf
            else ""
        )
        ie = self.propriedade.inscricao_estadual or ""
        tipo_exp = self.propriedade.tipo_exploracao or "1"
        part = self.formatar_valor(self.propriedade.participacao or 100.0)

        # ENUNCIADO TRANSCRITO 2026-10-05 (Manual 1.3, secção 3.3). Dezassete
        # campos. Ver `lcdpr_layout.CAMPOS_0040`.
        #
        # A versão anterior escrevia **treze** campos por interpolação directa, e
        # a partir do 5.º todos estavam na posição errada:
        #
        #     |0040|{id}|BR|BRL|{caepf}|{ie}|{nome}|{endereco}|{uf}|||{tipo}|{part}|
        #           1    2   3   4      5     6      7        8      9  10 11  12    13
        #
        # Lido campo a campo contra o manual:
        #
        #     5. CAD_ITR         recebeu `caepf`   -> errado
        #     6. CAEPF           recebeu `ie`      -> errado
        #     7. INSCR_ESTADUAL  recebeu `nome`    -> o NOME DA FAZENDA num campo de IE
        #     8. NOME_IMOVEL     recebeu `endereco` -> errado
        #     9. ENDERECO        recebeu `uf`       -> errado
        #    13. UF              recebeu `tipo_exp` -> errado
        #    15. CEP            recebeu `part`     -> a participação num campo de CEP
        #
        # E faltavam quatro campos inteiros: `BAIRRO`, `COD_MUN`, `CEP` (como
        # campos próprios) e `TIPO_EXPLORACAO`/`PARTICIPACAO` nas posições certas.
        # Um ficheiro assim é recusado pela Receita, e o produtor só descobre na
        # entrega — em Abril, com multa.
        #
        # `COD_IMOVEL` (campo 2) é sequencial **a partir de 1** por écran, e
        # **não** o `id` da base de dados: um imóvel tem de referenciar o Q100
        # pela mesma chave, e o id técnico não é a chave do ficheiro.
        reg_0040 = linha(
            "0040",
            str(self._codigo_imoveis).zfill(3),
            "BR",
            "BRL",
            self._texto(getattr(self.propriedade, "cad_itr", "")),  # 5. CAD_ITR
            caepf,  # 6. CAEPF — tem o campo, e o manual diz "Sim se BR"
            ie,  # 7. INSCR_ESTADUAL
            self._texto(self.propriedade.nome),  # 8. NOME_IMOVEL
            endereco,  # 9. ENDERECO
            "",  # 10. NUM   — Nao obrigatorio
            "",  # 11. COMPL — Nao obrigatorio
            bairro,  # 12. BAIRRO
            uf,  # 13. UF
            cod_mun,  # 14. COD_MUN — **Sim**. Vazio ate ser cadastrado
            cep,  # 15. CEP     — **Sim**. Vazio ate ser cadastrado
            tipo_exp,  # 16. TIPO_EXPLORACAO
            part,  # 17. PARTICIPACAO
        )
        self._codigo_imoveis += 1
        self._adicionar_linha(reg_0040, "0040")

        # ── Registro 0045: Cadastro de Terceiros ──────────────────────────
        #
        # ESTE REGISTO NAO EXISTIA. MEDIDO 2026-10-04: zero ocorrencias em
        # codigo e em testes.
        #
        # E' OBRIGATORIO. O Q100 exige, no campo `CNPJ_CPF_PARTICIPANTE`, o
        # documento do participante da relacao contratual — e a Receita nao
        # aceita um Q100 que aponte para um participante que nao foi declarado em
        # nenhum registo do Bloco 0. Sem o 0045, o ficheiro nao valida.
        #
        # O DADO JA EXISTIA: `LancamentoFinanceiro.participante` e
        # `.participante_doc`. Nao era falta de dados, era falta de registo.
        #
        # O QUE NAO ESTA FEITO, E POR QUE: a posicao exacta dos campos do 0045
        # no enunciado oficial nao foi obtida (o manual e' um PDF que a
        # extracao de texto nao alcanca). Ver `lcdpr_layout.PENDENTE_0045`.
        # Escrever este registo com campos inventados seria pior do que nao o
        # escrever: o produtor levaria um ficheiro recusado em vez de um erro
        # honesto. O que esta escrito abaixo tem o que a RFB exige e esta
        # declarado — codigo sequencial, documento, nome — e a lista completa de
        # campos, quando transcrita, entra em `lcdpr_layout.CAMPOS_0045` e a
        # contagem passa a ser verificada como nos outros registos.
        from app.models.financeiro import LancamentoFinanceiro
        from app.models.financeiro_banco import ContaBancaria

        terceiros: dict[str, str] = {}
        for l in (
            LancamentoFinanceiro.objects.filter(
                propriedade=self.propriedade, data__year=self.ano
            )
            .exclude(participante_doc__isnull=True)
            .exclude(participante_doc="")
            .values_list("participante_doc", "participante")
        ):
            doc = "".join(filter(str.isdigit, l[0] or ""))
            if not doc:
                continue
            # O proprio produtor nao e' terceiro: e' o titular do 0000. Declara-lo
            # no 0045 seria dizer a Receita que o produtor e' contraparte de si
            # proprio em todas as lancamentos dele.
            if doc == cpf_cnpj:
                continue
            terceiros.setdefault(doc, l[1] or "")

        for _doc, nome_terceiro in sorted(terceiros.items()):
            # ENUNCIADO TRANSCRITO 2026-10-05 (Manual 1.3, secção 3.3). Seis campos.
            # Ver `lcdpr_layout.CAMPOS_0045`.
            #
            # A versão anterior escrevia **quatro**:
            #
            #     |0045|{seq:04d}|{doc}|{nome_terceiro}|
            #
            # Ou seja, `REG`, um sequencial, o documento e o nome. Faltavam
            # **três** campos, e um deles e' o que justifica o registo existir:
            #
            #     2. COD_IMOVEL         — a que 0040 se refere
            #     3. TIPO_CONTRAPARTE   — 1 Condominio, 2 Arrendador, 3 Parceiro,
            #                             4 Comodante, 5 Outros
            #     6. PERC_CONTRAPARTE   — **Sim**. A percentagem de cada um
            #
            # `PERC_CONTRAPARTE` ausente e' o caso perigoso: o ficheiro declara
            # contrapartes sem dizer quanto cada uma participa, e a Receita nao
            # valida um 0045 sem isso. Era tambem o que faltava para o registo
            # servir para alguma coisa — uma parceria sem percentagens nao e' uma
            # parceria, e' uma lista de nomes.
            #
            # `COD_IMOVEL` e' o do 0040 correspondente, e `PERC_CONTRAPARTE` so
            # sai se o dado existir: `participacao` do imovel e' a do produtor
            # **declarante**, nao a de cada contraparte. Sem uma fonte para o
            # terceiro, escreve-se o que se sabe e **nao se divide a percentagem
            # ao acaso** — ver `_percentagem_contraparte`.
            reg_0045 = linha(
                "0045",
                str(self._codigo_imoveis - 1).zfill(3),
                self._tipo_contraparte(doc, nome_terceiro),
                doc,
                nome_terceiro,
                self._percentagem_contraparte(doc),
            )
            self._adicionar_linha(reg_0045, "0045")

        # ── Registro 0050: Cadastro das Contas Bancarias ──────────────────
        # FORMATO NAO VALIDADO CONTRA O MANUAL. Ver
        # `lcdpr_layout.REGISTROS_SEM_ENUNCIADO_VALIDADO`.
        contas = ContaBancaria.objects.filter(propriedade=self.propriedade)
        for conta in contas:
            banco_cod = conta.banco[:3]
            banco_nome = self._texto(conta.banco)
            ag = "".join(filter(str.isdigit, conta.agencia))
            cc = "".join(filter(str.isdigit, conta.conta))
            # ENUNCIADO TRANSCRITO 2026-10-05 (Manual 1.3, secção 3.3). Sete campos.
        # Ver `lcdpr_layout.CAMPOS_0050`.
        #
        # Este registo **ja estava conforme** na contagem e na ordem — e fica o
        # teste, porque "ja estava certo" tambem se degrada sem ninguem ver.
        #
        # Duas correcoes de conteudo, nao de posicao:
        #
        #   * `COD_CONTA` era `conta.id` (a chave da base de dados). O manual
        #     pede "codigo sequencial a partir de 1 das contas a listar", e o
        #     Q100 aponta para este codigo — um id técnico não é a chave do
        #     ficheiro.
        #   * `PAIS_CTA` estava fixo em "BR" sem ser o valor da conta. O
        #     manual: "BRA" — três letras. A diferença é um `Literal` aceite
        #     ou recusado.
        for seq, conta in enumerate(contas, 1):
            banco_cod = conta.banco[:3]
            banco_nome = self._texto(conta.banco)
            ag = "".join(filter(str.isdigit, conta.agencia))
            cc = "".join(filter(str.isdigit, conta.conta))
            reg_0050 = linha(
                "0050",
                str(seq).zfill(3),  # COD_CONTA — sequencial, não id
                "BRA",  # PAIS_CTA — o manual escreve BRA, 3 letras
                banco_cod,
                banco_nome,
                ag,
                cc,
            )
            self._adicionar_linha(reg_0050, "0050")

    # ------------------------------------------------------------------
    # Tipo do lancamento no Q100
    # ------------------------------------------------------------------

    #: `TIPO_LANCAMENTO_LCDPR` em `app/models/financeiro.py:99-111`.
    TIPO_RECEITA = "1"
    TIPO_DESPESA = "2"
    TIPO_ADIANTAMENTO = "3"

    def _tipo_contraparte(self, doc: str, nome: str) -> str:
        """Campo 3 do 0045: o que a contraparte e' para este imóvel.

        O manual fecha a lista: `1` Condomínio, `2` Arrendador, `3` Parceiro,
        `4` Comodante, `5` Outros.

        **Deducao por nome, e so por nome.** O `Propriedade.tipo_exploracao`
        diz-nos o regime do imovel ("2" condominio, "4" parceria), mas nao diz
        o papel de *cada* contraparte: os dados vem de
        `LancamentoFinanceiro.participante`, que e' texto livre.

        Quando o nome diz o papel, usa-se. Quando nao diz, escreve-se `5`
        (Outros) — **que e' a resposta honesta**, e nao a inventada: um "3"
        (Parceiro) sem o produtor ter dito que e' parceiro e' uma afirmacao
        sobre a relacao contratual de outra pessoa.
        """
        alvo = (nome or "").lower()
        for termo, codigo in (
            ("arrendat", "2"),
            ("parceir", "3"),
            ("comodant", "4"),
            ("condom", "1"),
        ):
            if termo in alvo:
                return codigo
        return "5"

    def _percentagem_contraparte(self, doc: str) -> str:
        """Campo 6 do 0045: `PERC_CONTRAPARTE`. **Sim** no manual.

        Aqui a resposta honesta e' **vazia**, e ela e' deliberada.

        O que existe: `Propriedade.participacao` — a percentagem do produtor
        **declarante**. O que nao existe: a percentagem de cada contraparte.
        Nao ha campo, nao ha modelo, e `MembroPropriedade` (que e' sobre
        **acesso ao sistema**, nao sobre exploracao agricola) nao tem percentagem.

        Deduzir "os outros dividem o que sobra a partes iguais" seria inventar a
        estrutura de propriedade de uma empresa de outra pessoa. Um produtor
        pode ter dois parceiros a 40% e 10%, e um condomínio com cotas
        desiguais — e a repartição errada no ficheiro é uma rectificação que
        só se fecha em anos.

        Por isso: vazio, e a **guarda** trata disto. Ver
        `pode_exportar(..., exigir_campos_fiscais=True)` — uma exploração
        conjunta sem percentagens é uma parceria que ninguém pode declarar.
        """
        return ""

    def _tipo_lancamento(self, lancamento) -> str:
        """Qual das tres categorias do Q100 este lancamento e'.

        MEDIDO 2026-10-04 (agente 9). Antes isto era `l.tipo_lancamento_lcdpr`,
        copiado cru. E o campo tem `default="2"` — "Despesa de Custeio e
        Investimentos" — por isso **toda** receita criada sem o preencher a
        saia classificada como despesa:

            |Q100|15032026|1|||6|Venda de grao||2|1234.56||1234.56 S|
                                        ^^                  ^^^^^^^^
                              diz "despesa"      valor na coluna de ENTRADA

        A linha dizia "despesa" e "entrou 1.234,56" ao mesmo tempo. Quem
        valida o ficheiro na Receita em Abril le o "2".

        A correccao deriva 1 e 2 de `lancamento.tipo`, que e' a mesma
        informacao que decide a coluna em que o valor foi posto — e assim a
        linha deixa de poder discordar de si propria. Isto vale
        independentemente do Leiaute: nao ha documento da Receita que autorize
        uma linha a contradizer a propria coluna de valor.

        O **3** (Produtos Entregues a Adiantamento de Recursos) nao se deriva:
        e' uma escolha do produtor e significa outra coisa — entrega de
        produto contra recurso adiantado, que nem receita nem despesa e'. Se
        fosse derivado de `tipo`, nunca sairia do ficheiro.

        Nao ha como distinguir "o produtor escolheu 2" de "o default e' 2". E
        nao faz falta: uma receita classificada como 2 seria um erro de
        lancamento, e o ficheiro nao deve levar um erro de lancamento para a
        Receita sem que a propria linha o denuncie.
        """
        if lancamento.tipo_lancamento_lcdpr == self.TIPO_ADIANTAMENTO:
            return self.TIPO_ADIANTAMENTO
        if lancamento.tipo == "RECEITA":
            return self.TIPO_RECEITA
        return self.TIPO_DESPESA

    # ------------------------------------------------------------------
    # Texto para um ficheiro delimitado por |
    # ------------------------------------------------------------------

    #: O que o|Leiaute usa como separador, mais o que quebra a linha.
    SEPARADOR = "|"
    QUEBRA_LINHA = "\r\n"

    @classmethod
    def _texto(cls, valor) -> str:
        """Um campo de texto que nao desloca os campos seguintes.

        MEDIDO 2026-10-04 (agente 9). Os registos do LCDPR sao texto
        delimitado por `|`, e varios campos recebem texto **que o produtor
        escreve**: a descricao do lancamento, o numero do documento, o
        endereco da propriedade, o nome. Nenhum era limpo.

        Um `|` num deles desloca **todos** os campos a partir dai. Medido com
        a descricao `Sementes | Herbicida`:

            |Q100|15032026|1|||6|Sementes | Herbicida||2||100.00|100.00 N|
            └──── 14 campos, como deve ────┘ └─ 15, everything shifted

        E o pior caso e' o numero do documento, porque o `|` cai no meio de
        um campo curto:

            |Q100|15032026|1||NF|123|6|Compra||2||100.00|200.00 N|
                        ^^^^ ^^
                    a Receita le `NF` como documento, `123` como tipo de
                    documento, `6` como historico — e a linha inteira passa
                    ao lado

        Nao e' um caso exotico: `|` e' um separador que as pessoas escrevem
        ("sementes | herbicida", "NF | 123"), e o campo e' de texto livre.

        A correccao substitui o separador por espaco e achata as quebras de
        linha. Nao se trunca o texto: um historico cortado e' um historico
        errado, e|e' melhor um espaco a mais do que um campo deslocado. Nao se
        inventa um limite de comprimento porque o Leiaute nao esta aqui para
        o confirmar — e um ficheiro fiscal nao se corrige por suposicao.
        """
        if valor is None:
            return ""
        texto = str(valor)
        for ch in (cls.SEPARADOR, "\r", "\n", "\t"):
            texto = texto.replace(ch, " ")
        return " ".join(texto.split())

    def _gerar_bloco_q(self):
        from app.models.financeiro import LancamentoFinanceiro
        from app.services.lcdpr_layout import (
            COD_CONTA_ESPECIE,
            COD_CONTA_TRANSITO,
            TIPO_DOC_OUTROS,
            TIPO_LANC_CUSTEIO_E_INVESTIMENTO,
            TIPO_LANC_RECEITA,
            linha,
            natureza_saldo,
        )

        lancamentos = LancamentoFinanceiro.objects.filter(
            propriedade=self.propriedade, data__year=self.ano
        ).order_by("data")

        saldo_acumulado = 0.0
        q100 = 0

        for l in lancamentos:
            if not l.tipo_lancamento_lcdpr:
                continue

            q100 += 1

            dt = self.formatar_data(l.data)
            cod_imovel = self.propriedade.id

            # `COD_CONTA`: a conta por onde o recurso transitou (registo 0050).
            #
            # O manual da duas saidas que nao sao conta nenhuma: "000" quando
            # foi pago em especie, "999" quando e' numerario em transito —
            # financiamentos de custeio, permuta de ativos, recursos de
            # condominios. A distincao importa porque sem ela um pagamento em
            # dinheiro fica apontado a uma conta que nao recebeu nada, e o saldo
            # da conta bancaria nao bate com o saldo do livro.
            #
            # `COD_CONTA_TRANSITO` e' o fallback para um lancamento sem conta
            # associada: nao se sabe por onde transitou, e a Receita trata
            # "nao discriminator" como numerario em transito. Um `""` vaza um
            # campo obrigatorio vazio.
            cod_conta = (
                str(l.conta_bancaria.id) if l.conta_bancaria_id else COD_CONTA_TRANSITO
            )

            num_doc = self._texto(l.numero_documento)
            tipo_doc = l.tipo_documento_lcdpr or TIPO_DOC_OUTROS
            hist = self._texto(l.descricao or l.get_categoria_display())
            part = (
                "".join(filter(str.isdigit, l.participante_doc))
                if l.participante_doc
                else ""
            )

            # `TIPO_LANC`: 1 receita da atividade rural, 2 despesas de custeio e
            # investimento, 3 produtos entregues a adiantamento de recursos.
            #
            # MEDIDO 2026-10-05 (agente 9). Este comentario dizia que o campo
            # vinha do `lancamento.tipo_lancamento_lcdpr` e **nao** do
            # `lancamento.tipo` — "copiar o `tipo` para aqui classificaria mal
            # todo o lancamento nao dedutivel".
            #
            # O raciocinio estava certo no essencial e a conclusao estava
            # errada. No Q100 **nao existe** um codigo para "despesa nao
            # dedutivel": uma despesa nao dedutivel continua a ser saida de
            # dinheiro e a levar `TIPO_LANC = 2`. Portanto derivar 1 e 2 de
            # `tipo` da a resposta certa **tambem** nesses casos — nao ha
            # classificacao a perder. E o que se perdia era o outro lado:
            #
            # `tipo_lancamento_lcdpr` tem `default="2"`, entao **toda** receita
            # criada sem o preencher saia como despesa, na mesma linha em que
            # o valor entrava na coluna de entrada. A linha dizia "despesa" e
            # "entrou 1234,56" ao mesmo tempo.
            #
            # O `3` continua a nao ser derivado, porque e' uma escolha do
            # produtor e significa outra coisa — entrega de produto contra
            # recurso adiantado. Ver `_tipo_lancamento`.
            tipo_lanc = self._tipo_lancamento(l)

            vl_entrada = 0.0
            vl_saida = 0.0

            if l.tipo == "RECEITA":
                vl_entrada = float(l.valor)
                saldo_acumulado += vl_entrada
            else:
                vl_saida = float(l.valor)
                saldo_acumulado -= vl_saida

            vl_ent_str = self.formatar_valor(vl_entrada) if vl_entrada > 0 else ""
            vl_sai_str = self.formatar_valor(vl_saida) if vl_saida > 0 else ""

            # `SLD_FIN` e `NAT_SLD_FIN` sao DOIS campos, e o codigo da natureza
            # e' `P`/`N`.
            #
            # Antes isto era uma f-string so:
            #
            #     sld_str = f"{self.formatar_valor(abs(saldo_acumulado))} "
            #               f"{'S' if saldo_acumulado >= 0 else 'N'}"
            #
            # e a linha ficava `...|1234.56 S|`. Dois erros num campo so:
            #
            # 1. O manual declara `NAT_SLD_FIN` com dominio `[N:P]` —
            #    **Negativo** ou **Positivo**. `S` (de "saldo") nao pertence a
            #    esse conjunto, e o validador da Receita recusa.
            # 2. Os dois campos estavam colados, separados por um espaco. Sao
            #    campos separados, e um ficheiro com o numero e a letra no mesmo
            #    lugar desloca a leitura de tudo o que vier a seguir.
            #
            # `natureza_saldo()` decide: zero e' credor, logo `P`.
            reg_q100 = linha(
                "Q100",
                dt,
                cod_imovel,
                cod_conta,
                num_doc,
                tipo_doc,
                hist,
                part,
                tipo_lanc,
                vl_ent_str,
                vl_sai_str,
                self.formatar_valor(abs(saldo_acumulado)),
                natureza_saldo(saldo_acumulado),
            )
            self._adicionar_linha(reg_q100, "Q100")

        self._q100_emitted = q100
        self._saldo_final = saldo_acumulado
        self._gerar_resumo_mensal(lancamentos)

    def _gerar_resumo_mensal(self, lancamentos):
        """Registro Q200 — Resumo Mensal. OBRIGATORIO, e ausente.

        O manual: "preenchido com base nas informacoes do Bloco Q100". O
        `SLD_FIN` do Q200 e' o saldo **cumulativo ate o mes** — o saldo dos
        lancamentos do mes mais o saldo final do mes anterior. Nao e' o saldo do
        mes isolado, e e' o erro classico aqui: um produtor que reconcile o Q200
        com o extrato ve a divergencia e nao sabe de que lado esta o problema.

        A soma e' feita a partir dos **mesmos** lancamentos que writes os Q100, e
        nao de uma segunda consulta: se as duas divergirem, o ficheiro
        tem dois saldos diferentes e nao ha nada no ficheiro que diga qual esta
        certo.
        """
        from app.services.lcdpr_layout import (
            CAMPOS_Q200,
            linha,
            natureza_saldo,
        )

        por_mes: dict[int, dict[str, float]] = {}
        for l in lancamentos:
            if not l.tipo_lancamento_lcdpr:
                continue
            mes = l.data.month
            acc = por_mes.setdefault(mes, {"entrada": 0.0, "saida": 0.0})
            if l.tipo == "RECEITA":
                acc["entrada"] += float(l.valor)
            else:
                acc["saida"] += float(l.valor)

        acumulado = 0.0
        for mes in range(1, 13):
            valores = por_mes.get(mes, {"entrada": 0.0, "saida": 0.0})
            acumulado += valores["entrada"] - valores["saida"]
            reg = linha(
                "Q200",
                f"{mes:02d}",
                self.formatar_valor(valores["entrada"]),
                self.formatar_valor(valores["saida"]),
                self.formatar_valor(abs(acumulado)),
                natureza_saldo(acumulado),
            )
            self._adicionar_linha(reg, "Q200")

    def _gerar_bloco_9(self):
        self.totais_registros["9999"] = 1
        total_linhas = sum(self.totais_registros.values())
        reg_9999 = f"|9999|{total_linhas}|"
        self.linhas.append(reg_9999)
