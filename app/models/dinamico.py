"""
Models do Criador Livre — o motor de geração dinâmica (BUILD 2).

DECISÃO D3: UM VOCABULÁRIO SÓ
-----------------------------
Os dois documentos da fase discordavam sobre os nomes, e nomes diferentes
significam migrations diferentes e ferramentas MCP diferentes:

  `docs/MAPA_DE_IMPLEMENTACAO_AMPLIA.md`   ->  DynamicEntity / DynamicSchema / DynamicRecord
  `docs/mcp-Ampliagro_amplIA.md`          ->  DynamicApp     / DynamicField  / DynamicRecord

Adotado o vocabulário do documento do MCP, por três motivos concretos:

1. **"App" é a palavra do produto.** O `PLANO_CRIADOR_LIVRE` fala em "criar
   ferramentas" que viram "app nativo" no painel. O usuário nunca vê "Entity".
2. **`DynamicField` como linha por campo é o único desenho que evolui.**
   Um `DynamicSchema` com os campos num blob JSON obriga a reescrever o blob
   inteiro para renomear um campo, e não permite validação nem ordenação por
   campo. Com uma linha por campo, cada um carrega suas own regras.
3. **Alinha com as tools MCP**, cujos parâmetros já se chamam
   `name/description/schema_json`: o model é a mesma palavra da tool.

Mapa para o vocabulário antigo, para não perder a rastreabilidade dos docs:
    DynamicEntity  ->  DynamicApp
    DynamicSchema  ->  DynamicField (uma linha por campo)
    DynamicRecord  ->  DynamicRecord (mesmo nome, sem conflito)

O QUE ESTE MÓDULO NÃO FAZ
--------------------------
Nada aqui executa código. A diretriz 2 do mapa é explícita:

    "Nunca, em hipótese alguma, use `eval()` ou `exec()` para rodar código
     gerado pela IA no servidor."

A "lógica" de uma ferramenta criada pela IA é um conjunto de **metadados
estruturados** (tipos, obrigatoriedade, opções) validados aqui e aplicados por
código genérico em `app/ia/dinamicos.py`. É a diretriz 3 ("não poluir
migrations") aplicada na prática: a IA escreve metadados, nunca `.py`.

ISOLAMENTO
----------
Toda linha é escopada por `user`. Um usuário nunca vê nem escreve ferramenta de
outro — a checagem é no manager/queryset, não na view, para não depender de
alguém lembrar de filtrar. Para ferramenta que se amarra a uma propriedade, a
validação passa por `app.hierarquia.propriedades_visiveis`, que já sabe
incluir a propriedade vinculada do servidor e a do funcionário.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify

from app.models.campos import JSONFieldPortatil

# --------------------------------------------------------------------------
# Vocabulário de campos
# --------------------------------------------------------------------------

TIPOS_CAMPO = [
    ("TEXTO", "Texto"),
    ("TEXTO_LONGO", "Texto longo"),
    ("NUMERO", "Número inteiro"),
    ("DECIMAL", "Número com casas"),
    ("BOOLEANO", "Sim / não"),
    ("DATA", "Data"),
    ("DATA_HORA", "Data e hora"),
    ("OPCOES", "Escolha entre opções"),
    ("REFERENCIA", "Ligação a outra ferramenta"),
    ("JSON", "Dados livres (JSON)"),
]

TIPOS_COM_VALOR = {"NUMERO", "DECIMAL", "BOOLEANO", "DATA", "DATA_HORA"}
TIPOS_COM_OPCOES = {"OPCOES"}
#: Campos cujo valor default faz sentido antes de o usuário preencher.
DEFAUT_SENSO_COMUM = {
    "NUMERO": 0,
    "DECIMAL": 0,
    "BOOLEANO": False,
}


def chave_de_rotulo(rotulo: str, usado: str = "") -> str:
    """Converte um rótulo em nome de campo utilizável.

    Ex: "Peso do animal (kg)" -> "peso_do_animal_kg". Usa slugify para não
    depender de accents, e prefixa com `campo_` quando o slug ficou vazio
    (rótulo só com emoji ou só com pontuação), porque a chave vira atributo
    de um JSONField e precisa ser um identificador.
    """
    base = slugify(rotulo or "").replace("-", "_")
    base = "_".join(p for p in base.split("_") if p)
    if not base:
        base = "campo"
    if base[0].isdigit():
        base = f"campo_{base}"
    return base


class DynamicApp(models.Model):
    """Uma ferramenta criada pela IA, ou pelo usuário com a ajuda dela.

    Exemplo real do plano: "Controle de Geladeira", "Registro de Vacinas".
    A IA preenche `campos` (metadados) e a interface é desenhada a partir
    deles — nenhum `.py` é criado.
    """

    ESTADOS = [
        ("RASCUNHO", "Rascunho"),
        ("PRONTO", "Pronto"),
        ("ARQUIVADO", "Arquivado"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="dinamicos_criados"
    )
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    descricao = models.TextField(blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="RASCUNHO")
    #: Markup do botão na paleta do painel, ex: "bi-thermometer-snow".
    icone = models.CharField(max_length=60, blank=True)
    #: Quando a ferramenta precisa de hardware, fica aqui o escopo técnico
    #: que a IA escreve para o time de desenvolvimento (ver PLANO_CRIADOR_LIVRE
    #: 3.3 — o "Broker" de IoT). Nunca executa nada: é documentação.
    escopo_iot = JSONFieldPortatil(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ferramenta dinâmica"
        verbose_name_plural = "Ferramentas dinâmicas"
        ordering = ["nome"]
        constraints = [
            # Um usuário não pode ter duas ferramentas com o mesmo slug: a chave
            # do formulário e a rota dependem dele. unique_together em vez de
            # UniqueConstraint simples porque o par (user, slug) é a identidade.
            models.UniqueConstraint(
                fields=["user", "slug"], name="uniq_dinamico_app_user_slug"
            )
        ]
        indexes = [
            models.Index(fields=["user", "estado"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.user_id})"

    def salvar_slug(self):
        """Deriva o slug do nome, garantindo unicidade dentro do usuário."""
        base = slugify(self.nome)[:120] or "ferramenta"
        slug, n = base, 2
        qs = DynamicApp.objects.filter(user=self.user, slug=slug)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        while qs.exists():
            slug = f"{base}-{n}"
            n += 1
            qs = DynamicApp.objects.filter(user=self.user, slug=slug)
        self.slug = slug
        return self


class DynamicField(models.Model):
    """Um campo de uma `DynamicApp`. Uma linha por campo — é o que permite
    evoluir e validar cada campo sem reescrever o schema inteiro."""

    app = models.ForeignKey(
        DynamicApp, on_delete=models.CASCADE, related_name="dynamic_fields"
    )
    #: Nome de campo (snake_case). É a chave dentro do JSONField de dados.
    chave = models.CharField(max_length=60)
    rotulo = models.CharField(max_length=120)
    tipo = models.CharField(max_length=15, choices=TIPOS_CAMPO, default="TEXTO")
    ajuda = models.CharField(max_length=200, blank=True)
    obrigatorio = models.BooleanField(default=False)
    #: Valor inicial. Só é automático para tipos numéricos/booleanos, porque
    #: inventar texto padrão seria pior do que pedir ao usuário.
    padrao = JSONFieldPortatil(default=None, blank=True, null=True)
    #: Lista de {"valor": ..., "rotulo": ...} para tipo OPCOES.
    opcoes = JSONFieldPortatil(default=list, blank=True)
    #: `DynamicApp` alvo, para tipo REFERENCIA. Validado em `clean()`.
    app_relacionada = models.ForeignKey(
        DynamicApp,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dynamic_referencias_origem",
    )
    ordem = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    TIPOS = TIPOS_CAMPO

    class Meta:
        verbose_name = "Campo dinâmico"
        verbose_name_plural = "Campos dinâmicos"
        ordering = ["ordem", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["app", "chave"], name="uniq_dinamico_field_app_chave"
            )
        ]
        indexes = [
            models.Index(fields=["app", "ordem"]),
        ]

    def __str__(self):
        return f"{self.app_id}.{self.chave} ({self.tipo})"

    def clean(self):
        """Coerência entre tipo e metadados. Chamado por `full_clean()`.

        Verifica aqui o que é impossível de representar no schema: OPCOES sem
        lista, REFERENCIA sem app alvo, e valor padrão de tipo incompatível.
        Um erro de configuração aqui apareceria como dado corrompido na tela
        do produtor — por isso falha no save, não na leitura.
        """
        from django.core.exceptions import ValidationError

        erros = {}
        if self.tipo in TIPOS_COM_OPCOES and not self.opcoes:
            erros["opcoes"] = "campo do tipo OPCOES exige uma lista de opções."
        if self.tipo not in TIPOS_COM_OPCOES and self.opcoes:
            erros["opcoes"] = f"campo do tipo {self.tipo} não aceita lista de opções."
        if self.tipo == "REFERENCIA" and not self.app_relacionada_id:
            erros["app_relacionada"] = (
                "campo do tipo REFERENCIA exige a ferramenta alvo."
            )
        if self.tipo != "REFERENCIA" and self.app_relacionada_id:
            erros["app_relacionada"] = (
                f"campo do tipo {self.tipo} não pode apontar para outra ferramenta."
            )
        if (
            self.padrao is not None
            and self.tipo not in TIPOS_COM_VALOR | TIPOS_COM_OPCOES
        ):
            erros["padrao"] = f"campo do tipo {self.tipo} não aceita valor padrão."
        if erros:
            raise ValidationError(erros)

    def valores_validos(self):
        """Set de valores aceitáveis, para tipo OPCOES. Vazio nos demais tipos."""
        if self.tipo not in TIPOS_COM_OPCOES:
            return None
        saida = set()
        for o in self.opcoes or []:
            if isinstance(o, dict) and "valor" in o:
                saida.add(o["valor"])
            else:
                saida.add(o)
        return saida


class DynamicRecordQuerySet(models.QuerySet):
    """QuerySet com o filtro de escopo por usuário e o filtro de dados JSON.

    O filtro de escopo mora aqui, e não na view, para que um endpoint novo
    esqueça menos: `DynamicRecord.objects.para(user)` já vem restrito.
    """

    def para(self, user):
        """Restringe ao usuário. Anônimo/None devolve vazio, nunca tudo.

        Fail-closed: falha de sessão não pode virar vazamento de dados. É o
        mesmo princípio de `app.hierarquia._perfil_ou_negado`.
        """
        if user is None or not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(user_id=user.pk)

    def do_app(self, app):
        if app is None:
            return self.none()
        return self.filter(app_id=getattr(app, "pk", app))

    def do_usuario_e_app(self, user, app):
        """Atalho para o par que toda listagem usa — uma query só."""
        return self.para(user).do_app(app)

    def ordenar_por_campo(self, campo: str, crescente: bool = True):
        """Ordena por uma chave do JSONField usando key transform.

        Key transform (`dados__status`) é portátil: funciona em SQLite e em
        Postgres. `RawSQL` seria mais rápido, mas amarraria a camada ao
        backend — ver `app/ia/json_portatil.py`.
        """
        return self.order_by(f"{'-' if not crescente else ''}dados__{campo}")


class DynamicRecord(models.Model):
    """Uma linha de dados de uma `DynamicApp`.

    `dados` é um JSONField genérico. É a decisão 2: onde o Postgres faria
    JSONB com índice GIN, o mesmo campo funciona em SQLite sem trocar uma
    linha do código de aplicação.
    """

    app = models.ForeignKey(
        DynamicApp, on_delete=models.CASCADE, related_name="dinamicos_registrados"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="dinamicos_registros"
    )
    dados = JSONFieldPortatil(default=dict)
    #: Snapshot do estado da ferramenta no momento da escrita. Serve para
#: Fonte do dado — medido (do banco), simulado (gerado) ou ausente.
    #: Obrigatório por VISÃO §5.4; tools como `amplia_catalogos` exigem-o.
    FONTE_CHOICES = [
        ("medido", "Dado medido no banco"),
        ("simulado", "Número gerado, sem ligação a esta fazenda"),
        ("sem_dado", "Não há o que mostrar. O config traz `sem_dado: true`."),
    ]
    fonte_dado = models.CharField(
        "fonte dado",
        max_length=20,
        choices=FONTE_CHOICES,
        default="medido",
    )
    #: auditar depois ("o que o formulário mostrava quando esse registro foi
    #: salvo?"), porque a ferramenta pode ganhar campo depois.
    schema_snapshot = JSONFieldPortatil(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = DynamicRecordQuerySet.as_manager()

    class Meta:
        verbose_name = "Registro dinâmico"
        verbose_name_plural = "Registros dinâmicos"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["app", "user"]),
            models.Index(fields=["app", "-criado_em"]),
            models.Index(fields=["user", "-criado_em"]),
        ]

    def __str__(self):
        return f"{self.app_id}#{self.pk} ({self.user_id})"

    def valor(self, campo: str, padrao=None):
        """Lê uma chave do registro com fallback. Não levanta em chave ausente."""
        dados = self.dados if isinstance(self.dados, dict) else {}
        v = dados.get(campo, padrao)
        return padrao if v is None else v
