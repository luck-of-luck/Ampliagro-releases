from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.validators import validate_json_safe

BIOMAS = [
    ("amazonia", "Amazônia"),
    ("cerrado", "Cerrado"),
    ("mata_atlantica", "Mata Atlântica"),
    ("caatinga", "Caatinga"),
    ("pampa", "Pampa"),
    ("pantanal", "Pantanal"),
]


class Cultura(models.Model):
    GRUPOS = [
        ("graos", "Grãos"),
        ("frutas", "Frutas"),
        ("citricos", "Cítricos"),
        ("hortalicas", "Hortaliças"),
        ("tuberculos", "Tubérculos e Raízes"),
        ("ervas", "Ervas e Aromáticas"),
        ("leguminosas", "Leguminosas"),
        ("oleaginosas", "Oleaginosas"),
        ("frutas_bosque", "Frutas de Bosque"),
        ("especiarias", "Especiarias"),
        ("medicinais", "Plantas Medicinais"),
        ("panc", "PANC"),
        ("trepadeiras", "Trepadeiras e Videiras"),
        ("cana", "Cana-de-açúcar"),
        ("fibras", "Fibras"),
        ("nativas", "Árvores Nativas"),
        ("forrageiras", "Forrageiras"),
        ("pastagem", "Pastagem"),
        ("florestal", "Florestal"),
        # ── Pecuária e aquicultura ──
        # MEDIDO em 13/10/2026: a base tem 709 culturas em 30 valores de
        # `grupo` distintos, mas esta lista só declarava 20. Faltavam 12,
        # e nenhum deles era nicheado — eram as espécies que o produtor
        # bookshelf de facto: 249 culturas, das quais 69 em `peixes`, 41 em
        # `bovinos`, 26 em `ovinos`, 22 em `suinos`, 25 em `crustaceos`, 21
        # em `equinos`, 18 em `aves`, 16 em `infraestrutura`, 5 em `bufalos`,
        # 4 em `leite`, 1 em `ovos` e 1 em `perenes`.
        #
        # Sem estes rótulos, `dict(Cultura.GRUPOS)` (usado por
        # `app.cultures.seletor` e pelo admin) caía no valor cru e o produtor
        # lia "peixes" e "bovinos" no lugar de "Peixes" e "Bovinos". Não é
        # crash — é pior: parece funcionar.
        ("bovinos", "Bovinos"),
        ("bufalos", "Búfalos"),
        ("ovinos", "Ovinos"),
        ("suinos", "Suínos"),
        ("equinos", "Equinos"),
        ("aves", "Aves"),
        ("leite", "Produção de Leite"),
        ("ovos", "Produção de Ovos"),
        ("perenes", "Raças Perenes"),
        # ── Aquicultura ──
        ("peixes", "Peixes"),
        ("crustaceos", "Crustáceos"),
        # ── Infraestrutura ──
        # Não é cultura. A base tem 16 linhas aqui (pivô, casa, curral…) e
        # elas são usáveis na pesquisa e em safras, por isso ficam
        # declaradas. O rótulo diz o que são, para ninguém as contar como
        # produção vegetal.
        ("infraestrutura", "Infraestrutura"),
        ("outro", "Outro"),
    ]
    nome = models.CharField(max_length=100)
    grupo = models.CharField(max_length=20, choices=GRUPOS, default="outro")
    unidade_comercial = models.CharField(max_length=50, default="sacas")
    janela_plantio_inicio = models.IntegerField(null=True, blank=True)
    janela_plantio_fim = models.IntegerField(null=True, blank=True)
    chave_mercado = models.CharField(max_length=100, blank=True)
    ibge_codigo = models.IntegerField(
        null=True, blank=True, help_text="Código IBGE SIDRA (classificação 782)"
    )
    agrodoc_produto = models.CharField(
        max_length=50, blank=True, help_text="Nome do produto na API AgroDoc"
    )
    ciclo_dias = models.IntegerField(
        null=True, blank=True, help_text="Ciclo médio em dias"
    )
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Cultura"
        verbose_name_plural = "Culturas"
        ordering = ["nome"]


#: As duas formas de apuracao do resultado rural, e o que cada uma quer dizer.
#: Os valores sao os que o registo 0010 do LCDPR espera — ver
#: `app/services/lcdpr_layout.py::CAMPOS_0010`.
FORMAS_APURACAO_CHOICES = [
    (
        "1",
        "Livro Caixa — apura pelo que entrou e saiu (VL_ENTRADA / VL_SAIDA)",
    ),
    (
        "2",
        "20% da receita bruta — art. 5o da Lei 8.023/1990",
    ),
]


class Propriedade(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="propriedades"
    )
    nome = models.CharField(max_length=100)
    area_total = models.DecimalField(max_digits=10, decimal_places=2)
    uf = models.CharField(max_length=2, default="MT")
    cidade = models.CharField(max_length=100, blank=True)
    endereco = models.TextField(blank=True)
    bioma = models.CharField(max_length=20, choices=BIOMAS, blank=True)
    pais = models.CharField(max_length=50, default="Brasil")
    moeda = models.CharField(max_length=3, default="BRL")
    culturas = models.ManyToManyField(
        "Cultura", related_name="propriedades", blank=True
    )
    # Marca de que o produtor RESPONDEU ao seletor de culturas, mesmo que a
    # resposta tenha sido "nenhuma".
    #
    # Sem esta coluna, "escolheu zero" e "nunca foi perguntado" são o mesmo
    # dado: zero linhas em `app_culturas_propriedades`. E as duas precisam de
    # comportamento oposto — a primeira esvazia a guia, a segunda não pode
    # esvaziá-la (ou todas as contas criadas antes do cadastro perdiam o
    # produto em silêncio). Derivar o estado do dado é o que produz o bug;
    # por isso o estado é gravado.
    #
    # `null=True` é o que diz "ainda não perguntado". Ver
    # `app/cultures/filtro.py::ids_escolhidos`, que é onde isto é lido.
    culturas_escolhidas_em = models.DateTimeField(null=True, blank=True)

    # LCDPR Fields
    cadastro_fiscal = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dados do contribuinte, contador e contrapartes para revisão do LCDPR.",
    )
    cpf_cnpj = models.CharField(
        max_length=18, blank=True, help_text="CPF ou CNPJ do produtor rural (LCDPR)"
    )
    caepf = models.CharField(
        max_length=15,
        blank=True,
        help_text="Cadastro de Atividade Econômica da Pessoa Física (LCDPR)",
    )
    inscricao_estadual = models.CharField(max_length=20, blank=True)
    TIPO_EXPLORACAO_CHOICES = [
        ("1", "Exploração Individual"),
        ("2", "Condomínio"),
        ("3", "Imóvel Arrendado"),
        ("4", "Parceria"),
        ("5", "Comodato"),
        ("6", "Outros"),
    ]
    tipo_exploracao = models.CharField(
        max_length=2,
        choices=TIPO_EXPLORACAO_CHOICES,
        default="1",
        help_text="Tipo de exploração para LCDPR (Reg 0040)",
    )
    participacao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100.0,
        help_text="Percentual de participação na propriedade",
    )
    # --- F08: a forma de apuracao e' DO PRODUTOR --------------------
    #
    # O registo 0010 do LCDPR diz a Receita se a apuracao foi pelo Livro
    # Caixa ("1") ou pelos 20% da receita bruta do art. 5o da Lei
    # 8.023/1990 ("2"). Sao resultados diferentes e so o produtor sabe qual
    # e' o dele — ate aqui o sistema escrevia "1" para toda a gente, sem perguntar.
    #
    # `default="1"` mantem o comportamento actual para quem nunca preencheu:
    # nenhuma ficha existente muda. O que muda e' que agora a escolha existe.
    #
    # `blank=False` e' deliberado: um registo 0010 tem de levar uma forma. O
    # default ja garante isso. `blank=True` aqui permitiria gravar vazio e
    # produzir um 0010 sem conteudo — que e' o ficheiro invalido que o
    # `lcdpr_export` existe para impedir.
    forma_apuracao = models.CharField(
        max_length=1,
        choices=FORMAS_APURACAO_CHOICES,
        default="1",
        help_text="Forma de apuracao do resultado rural (registo 0010 do LCDPR)",
    )

    # --- Geolocalizacao ---
    # latitude/longitude: preenchidas por geocodificacao (Open-Meteo, sem chave).
    # `clima` e `geocode` em app/api/views/production.py JA usavam prop.latitude e
    # prop.longitude, mas os campos nao existiam — os dois endpoints quebravam com
    # AttributeError. Nullable de proposito: quem nao tem coordenada nao tem clima.
    latitude = models.FloatField(
        null=True, blank=True, help_text="Latitude em graus decimais"
    )
    longitude = models.FloatField(
        null=True, blank=True, help_text="Longitude em graus decimais"
    )
    # Contorno desenhado no mapa do onboarding, em GeoJSON (Polygon/MultiPolygon).
    # A area NAO e lida daqui: area_total continua sendo digitada pelo produtor ate
    # o calculo geodesico entrar (app/api/views/production.py:443 ainda faz area_ha=None).
    geometria = models.JSONField(
        default=dict,
        blank=True,
        help_text="GeoJSON do contorno da propriedade (Polygon/MultiPolygon)",
    )

    data_cadastro = models.DateTimeField(auto_now_add=True)

    # ─────────────────────────────────────────────────────────────────
    # Endereco e identificadores fiscais — MEDIDO 2026-10-05
    # ─────────────────────────────────────────────────────────────────
    #
    # Estes campos nao sao uma feature. Sao o que faltava para o ficheiro
    # do LCDPR poder sair correcto, e a razao esta escrita no enunciado.
    #
    # O QUE O MANUAL EXIGE, e o que o modelo tinha
    # ===============================================
    # Enunciado do LCDPR 1.3 transcrito em 2026-10-05 (Manual de
    # Preenchimento do LCDPR 1.3, Receita Federal, secao 3.3):
    #
    # | registo | campo    | obrigatorio? | o que o modelo tinha      |
    # |---------|----------|--------------|---------------------------|
    # | 0030    | COD_MUN  | **Sim**      | `cidade` (nome, nao codigo)|
    # | 0030    | CEP      | **Sim**      | nada                      |
    # | 0030    | BAIRRO   | **Sim**      | nada                      |
    # | 0030    | NUM_TEL  | Nao          | nada                      |
    # | 0040    | CAD_ITR  | Sim se BR    | nada                      |
    #
    # `cidade` e' o **nome** do municipio. `COD_MUN` e' o **codigo IBGE**,
    # sete digitos, de uma tabela da Receita. Sao coisas diferentes e nao se
    # derivam uma da outra sem a tabela — e por isso os dois sao campos.
    #
    # PORQUE VAO AGORA, E NAO DA PRIMEIRA VEZ
    # ==========================================
    # Porque o gerador ja escreve estes campos (`lcdpr_export.py`), a guarda ja
    # os exige (`pode_exportar(exigir_campos_fiscais=True)`), e **sem estes
    # campos no modelo a guarda nunca tem o que ler** — seria uma regra que
    # dispara sempre, sobre campos que nao existem.
    #
    # Este e' o inverso do padrao que este projecto evita. Noutros sitios o
    # modelo cresce e o gerador atrasa; aqui o gerador crescia e o modelo
    # faltava, e o resultado era um ficheiro fiscal com `COD_MUN` vazio que a
    # Receita recusa. **Sem o campo, a unica opcao honesta era recusar
    # exportar** — e era o que se passava.

    #: Codigo IBGE do municipio, **7 digitos**. Vai para `COD_MUN` em 0030 e
    #: 0040, que o manual marca como **Sim**. Tabela da Receita:
    #: sped.rfb.gov.br/pasta/show/1932
    cod_municipio = models.CharField(
        max_length=7,
        blank=True,
        help_text=(
            "Codigo IBGE do municipio, 7 digitos (Manual do LCDPR 1.3, campo "
            "COD_MUN dos registos 0030 e 0040). **Obrigatorio** no ficheiro "
            "fiscal. Nao e' o nome do municipio: e' o codigo. Vem da tabela da "
            "Receita (sped.rfb.gov.br/pasta/show/1932)."
        ),
    )

    #: CEP, **8 digitos**, so numericos. `CEP` em 0030 e 0040, **Sim**.
    cep = models.CharField(
        max_length=8,
        blank=True,
        help_text=(
            "CEP da propriedade, so digitos (8). Campo CEP dos registos 0030 e "
            "0040 do LCDPR 1.3 — **obrigatorio** no ficheiro fiscal."
        ),
    )

    #: Bairro. `BAIRRO` em 0030 e 0040, **Sim**.
    bairro = models.CharField(
        max_length=100,
        blank=True,
        help_text="Bairro ou distrito. Campo BAIRRO dos registos 0030 e 0040 do LCDPR 1.3.",
    )

    #: Telefone, so digitos (DDD + numero). `NUM_TEL` em 0030, **Nao** obrigatorio.
    telefone = models.CharField(
        max_length=15,
        blank=True,
        help_text="Telefone de contacto, so digitos (DDD + numero). Campo NUM_TEL do registo 0030 — opcional.",
    )

    #: CAD_ITR — o codigo do imovel no Cadastro Imobiliario Nacional.
    #: Campo 5 do 0040; o manual diz "Sim se o imovel estiver em zona rural e
    #: `0040.PAIS = BR`", que e' sempre o caso de uma propriedade rural.
    #:
    #: Distinto do CAEPF: o CAEPF identifica a **atividade economica da pessoa
    #: fisica** (IN RFB 1.828/2018) e o CAD_ITR identifica o **imovel**. Sao
    #: dois registos diferentes para nao se trocarem — e `caepf` ja existia,
    #: por isso o risco de confusao e' real.
    cad_itr = models.CharField(
        max_length=8,
        blank=True,
        help_text=(
            "CAD_ITR com digito verificador (8): o codigo do imovel no "
            "Cadastro Imobiliario Nacional. Campo 5 do registo 0040. **Nao e' "
            "o CAEPF** — esse identifica a atividade da pessoa fisica."
        ),
    )

    def __str__(self):
        return f"{self.nome} - {self.uf}"

    class Meta:
        verbose_name = "Propriedade"
        verbose_name_plural = "Propriedades"
        ordering = ["nome"]


class MembroPropriedade(models.Model):
    """Uma pessoa com acesso a uma propriedade, e com que papel.

    MEDIDO 2026-10-05 (agente 7). Antes disto o acesso era **propriedade de
    uma pessoa**: `Propriedade.user` e' um `ForeignKey`, e `user.propriedades`
    sao as fazendas *dele*. Nao havia lugar para mais ninguem.

    O tecto era literal, e medido — `app/hierarquia.py:207`:

        def propriedades_visiveis(user):
            qs = Propriedade.objects.filter(user=user)
            if perfil.propriedade_vinculada_id:      # no max. UMA
                vinc.append(...)
            if perfil.funcionario.propriedade_id:    # no max. UMA
                vinc.append(...)
            ...
            # => 1 propria + 1 + 1 = 3. Tecto duro, sem excecao.

    Tres e' um numero pequeno o suficiente para passar despercebido e grande
    o suficiente para fechar o produto. Um agronomo com 12 clientes, um
    contador que serve 40perties, uma familia com 4 fazendas — todos batem
    num tecto de 3. E o modo como os concorrentes crescem e' exactamente
    este: o Aegro vende "gerencie multiplos clientes com eficiencia", e a
    Lucro Rural vende "produtor **e** contador" como doispapéis na mesma
    propriedade.

    Este modelo e' a mudanca de esquema com maior retorno de produto do
    `docs/sistema/7.md`. Nao adiciona uma feature: **remove um tecto**.

    O QUE ESTE MODELO **NAO** FAZ
    ============================
    - Nao concede acesso. Um membro sem papel nao ve nada; ver
      `app/hierarquia.py:propriedades_visiveis`, que e' a unica porta.
    - Nao substitui o dono. `Propriedade.user` continua a ser o dono, e o
      dono continua a ter acesso implicitamente, sem precisar de linha.
    - Nao copia permissao. O `papel` aqui e' *escopo* (ver/editar); a
      permissao fina continua a ser `pode_ver_financeiro` e
      `PodeVerFinanceiro`, que ja sabiam de onde vinham.
    """

    PAPEL_CHOICES = [
        ("DONO", "Dono"),
        ("ADMIN", "Administrador"),
        ("AGRONOMO", "Agronomo"),
        ("CONTADOR", "Contador"),
        ("OPERADOR", "Operador de campo"),
        ("CONSULTOR", "Consultor (leitura)"),
    ]

    propriedade = models.ForeignKey(
        Propriedade, on_delete=models.CASCADE, related_name="membros"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="membros_propriedade"
    )
    papel = models.CharField(max_length=16, choices=PAPEL_CHOICES, default="CONSULTOR")

    # Uma propriedade so tem um dono, e esse dono e' `Propriedade.user`. Esta
    # constraint existe para `DONO` nunca duplicar: dois donos com o mesmo poder
    # na mesma propriedade nao tem leitura, e o `unique_together` abaixo
    # transformava essa ambiguidade num erro de base de dados em vez de uma
    # decisao de quem Cadastro > Equipe devolve "esta propriedade ja tem dono".
    _donho_unico = models.BooleanField(default=False)

    data_convite = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True)

    class Meta:
        verbose_name = "Membro da Propriedade"
        verbose_name_plural = "Membros das Propriedades"
        ordering = ["propriedade__nome", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["propriedade", "user"],
                name="uniq_membro_por_propriedade_user",
            ),
            models.UniqueConstraint(
                fields=["propriedade"],
                condition=models.Q(papel="DONO", _donho_unico=True),
                name="uniq_dono_por_propriedade",
            ),
        ]
        indexes = [models.Index(fields=["user", "ativo"])]

    def __str__(self):
        return f"{self.user.get_username()} em {self.propriedade.nome} ({self.papel})"


class Talhao(models.Model):
    propriedade = models.ForeignKey(
        "Propriedade", on_delete=models.CASCADE, related_name="talhoes"
    )
    nome = models.CharField(max_length=100)
    area_hectare = models.DecimalField(max_digits=8, decimal_places=2)
    cultura_atual = models.ForeignKey(
        "Cultura", on_delete=models.SET_NULL, null=True, blank=True
    )
    tipo_solo = models.CharField(max_length=50, blank=True)
    coordenadas = models.JSONField(default=dict, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} ({self.area_hectare} ha)"

    class Meta:
        verbose_name = "Talhão"
        verbose_name_plural = "Talhões"
        ordering = ["propriedade", "nome"]
        indexes = [
            models.Index(fields=["propriedade", "nome"]),
        ]


class TalhaoGeometria(models.Model):
    talhao = models.OneToOneField(
        "Talhao", on_delete=models.CASCADE, related_name="geometria"
    )
    geojson = models.JSONField(help_text="GeoJSON Feature (Polygon/MultiPolygon)")
    area_calculada_ha = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True
    )
    centroide_lat = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )
    centroide_lon = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Geometria do Talhão"
        verbose_name_plural = "Geometrias dos Talhões"

    def __str__(self):
        return f"Geometria: {self.talhao.nome}"


class AnaliseSolo(models.Model):
    talhao = models.ForeignKey(
        Talhao, on_delete=models.CASCADE, related_name="analises_solo"
    )
    data_coleta = models.DateField()
    ph = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fosforo_p = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, help_text="P em mg/dm³"
    )
    potassio_k = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="K em cmolc/dm³",
    )
    calcio_ca = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Ca em cmolc/dm³",
    )
    magnesio_mg = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Mg em cmolc/dm³",
    )
    aluminio_al = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Al em cmolc/dm³",
    )
    materia_organica_mo = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text="MO em %"
    )
    ctc = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Capacidade de Troca Catiônica",
    )
    saturacao_bases_v = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="V% (Saturação por bases)",
    )
    laboratorio = models.CharField(max_length=150, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        verbose_name = "Análise de Solo"
        verbose_name_plural = "Análises de Solo"
        ordering = ["-data_coleta"]


class AreaPreservacao(models.Model):
    TIPO_CHOICES = [
        ("APP", "Área de Preservação Permanente"),
        ("RL", "Reserva Legal"),
        ("OUTRO", "Outra Proteção"),
    ]
    propriedade = models.ForeignKey(
        Propriedade, on_delete=models.CASCADE, related_name="areas_preservacao"
    )
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    area_hectare = models.DecimalField(max_digits=10, decimal_places=2)
    geojson = models.JSONField(blank=True, default=dict)

    class Meta:
        verbose_name = "Área de Preservação"
        verbose_name_plural = "Áreas de Preservação"
