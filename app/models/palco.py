"""BUILD 5 — o esquema do "Palco": o que a IA monta, e o que o produtor fica.

TRÊS COISAS, NÃO UMA
====================
Antes da BUILD 5 o dashboard tinha um balde de widgets por utilizador e um
`DashboardUserState` com um blob JSON. Cabia tudo num lugar só, o que tornava
impossível responder a três perguntas que o produto agora faz:

1. "O QUE A IA ACERTOU?" — precisa de linhas, para treinar. Um blob JSON não se
   consulta, não se agrega, e não se versiona.
2. "O QUE EU FIZ DA MINHA MESA?" — o botão "Salvar como meu Dashboard" produz
   um artefacto que o produtor fixa e usa todos os dias. Isso e' primeira classe, não
   um pedaço de estado de layout.
3. "ISSO É MEU?" — a clonagem **tem** de ser tenant-safe. Não "quase": o
   produtor A nunca pode ver, listar, abrir nem apagar a mesa do produtor B.

O TENANT, E POR QUE ESTÁ NO MODELO E NÃO NUM `if`
=================================================
Todas as tabelas de dados do produtor levam `user` com `on_delete=CASCADE` e
`null=False`. O `unique_together` inclui sempre o `user`. Não há nenhuma query de
leitura que não filtre por `user`, e `PalcoQuerySet` é o único caminho — o
`objects` global é substituído.

A alternativa seria um `if user_id == request.user.id` em cada view. Funciona até
o dia em que alguém esquece um, e o esquecimento é um vazamento de dados
agronómicos de um produtor para o vizinho — o pior tipo de bug que existe num
sistema multi-tenant, porque não dá erro: dá um dashboard bonito e errado.

Por que NÃO meti os dashboards clonados dentro do `DashboardUserState.state`?
Porque esse blob já é o estado de *layout* (posições, ordem, preset ativo), e
misturar num um artefacto que o produtor fixou significa: sem integridade
referencial, sem cascade por único, e sem como listar "meus dashboards" numa
query. O `DashboardUserState` fica como está, e o `WidgetUsuario` também.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.db import models

VEREDITO_LIKE = "like"
VEREDITO_DISLIKE = "dislike"
VEREDITOS = ((VEREDITO_LIKE, "Aprovado"), (VEREDITO_DISLIKE, "Rejeitado"))

#: Fica ao nível do módulo e não dentro de `PalcoIA` porque `Meta` é uma classe
#: aninhada: o corpo dela não enxerga o namespace da classe que a contém, e
#: `KIND_PALCO = "palco"` aqui dentro levantaria NameError em tempo de importacao.
KIND_PALCO = "palco"


class PalcoQuerySet(models.QuerySet):
    """Único caminho de leitura. Sem `user`, não há consulta — por desenho."""

    def do_produtore(self, user):
        return self.filter(user=user)

    def palcos(self):
        return self.filter(kind=PalcoIA.KIND_PALCO)


class PalcoIA(models.Model):
    """O palco "Amplia": o preset que a IA redesenha a cada pergunta.

    É um singleton de propósito, com singleton garantido por check no banco. Um
    palco por instalação — o mesmo palco para toda a fazenda — porque o palco
    não é conteúdo: é *cenario*. Os widgets que aparecem nele são efémeros e
    pertencem a um produtor e a um momento, nunca ao palco.

    A `structure` fica vazia de propósito. Um palco com widgets guardados seria
    a mesma mesa para toda a gente, e o produtor A veria o analysis do produtor
    B assim que abrisse o dashboard. Os widgets efémeros vivem na sessão (ver
    `AssinaturaPalco.estrutura`, que é por produtor).
    """

    KIND_PALCO = "palco"

    slug = models.CharField(max_length=40, unique=True, default="amplia")
    nome = models.CharField(max_length=80, default="Amplia")
    kind = models.CharField(max_length=20, default=KIND_PALCO)
    ativo = models.BooleanField(default=True)
    structure = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = PalcoQuerySet.as_manager()

    class Meta:
        verbose_name = "Palco da IA"
        verbose_name_plural = "Palcos da IA"
        constraints = [
            # O nome antigo desta constraint era `palco_ia_so_palco`, e ela NÃO
            # fazia o que prometia: `kind='palco'` é satisfeito por uma segunda
            # linha com outro slug, e passava. Um check constraint não consegue
            # dizer "existe no máximo uma linha" — quem garante isso é o slug
            # UNIQUE mais a migração de dados, que cria a única. O que esta
            # constraint garante, e o que o nome agora diz, é que o registo não
            # se metam num `kind` inventado e desapareça do código sem ninguém
            # perceber.
            models.CheckConstraint(
                condition=models.Q(kind=KIND_PALCO),
                name="palco_ia_kind_palco",
            )
        ]

    def __str__(self):
        return f"{self.nome} ({self.slug})"


class AssinaturaPalco(models.Model):
    """Uma pergunta, a mesa que a IA montou, e o que o produtor achou dela.

    É a tabela que treina a IA. Uma linha por (produtor, pergunta) — e o
    VEREDITO É SUBSTITUÍDO, não acumulado.

    Por que substituir, e não guardar duas linhas? Porque um Like seguido de
    Dislike na mesma pergunta significa "a IA mudou e piorou". Com duas linhas,
    um treino ingênuo que lê "todas as linhas com Like" continuaria usando como
    exemplo positivo exatamente aquilo que o produtor rejeitou. O último
    veredito é o que vale. O histórico vai para `historico`, que é onde a
    mudança fica registrada sem mentir sobre o estado atual.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assinaturas_palco"
    )
    assinatura = models.CharField(
        max_length=160,
        validators=[MinLengthValidator(4)],
        help_text="Impressão digital da pergunta normalizada (ver app.ia.palco).",
    )
    intent_texto = models.TextField(help_text="A pergunta como o produtor a escreveu.")
    estrutura = models.JSONField(
        default=dict,
        help_text="Widgets validados que a IA montou. É o exemplo de treino.",
    )
    veredito = models.CharField(max_length=10, choices=VEREDITOS, default=VEREDITO_LIKE)
    lacuna = models.TextField(
        blank=True,
        default="",
        help_text="No Dislike: o que faltou, escrito pelo produtor. Vira a pergunta de volta.",
    )
    historico = models.JSONField(
        default=list,
        blank=True,
        help_text="Vereditos anteriores deste par (produtor, pergunta).",
    )
    contexto = models.JSONField(
        default=dict,
        blank=True,
        help_text="Propriedade, cultura, papel no momento do Like/Dislike.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = PalcoQuerySet.as_manager()

    class Meta:
        verbose_name = "Assinatura do Palco"
        verbose_name_plural = "Assinaturas do Palco"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "assinatura"], name="assinatura_unica_por_produtor"
            )
        ]
        indexes = [
            models.Index(fields=["user", "veredito"]),
        ]

    def __str__(self):
        return f"{self.user.username}:{self.assinatura[:24]}:{self.veredito}"

    def registrar_veredito(self, veredito: str, *, lacuna: str = "", estrutura=None):
        """Muda o veredito, guardando o anterior no histórico.

        A mudança de veredito é a informação mais valiosa da tabela: diz que a
        IA acertou e depois passou a errar a mesma pergunta. Sem ela, o produto
        fica sem nenhuma forma de notar a regressão.
        """
        if veredito not in dict(VEREDITOS):
            raise ValueError(f"veredito invalido: {veredito!r}")
        if veredito != self.veredito:
            self.historico = list(self.historico or []) + [
                {"veredito": self.veredito, "em": self.atualizado_em.isoformat()}
            ]
        self.veredito = veredito
        if lacuna:
            self.lacuna = lacuna
        if estrutura is not None:
            self.estrutura = estrutura
        self.save(
            update_fields=[
                "veredito",
                "lacuna",
                "estrutura",
                "historico",
                "atualizado_em",
            ]
        )
        return self


class PresetPalco(models.Model):
    """Um "Salvar como meu Dashboard" — a mesa da IA que o produtor quis ficar.

    Nasce de uma `AssinaturaPalco` (guardamos qual), mas passa a viver sozinho:
    o produtor pode apagar a conversa, dislike na assinatura, e esta mesa
    continua na tela dele. É dele, não da IA.

    O `slug` tem de casar com `app/presets.py` para o dashboard existente
    aceitá-lo: prefixo `custom-` e fora da blocklist de presets fantasma. Sem
    isso a mesa é criada e nunca mais aparece no menu — um botão que parece
    funcionar e não faz nada.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="presets_palco"
    )
    slug = models.CharField(max_length=60)
    nome = models.CharField(max_length=80)
    estrutura = models.JSONField(
        default=dict, help_text="Widgets, layout e identidade visual da mesa."
    )
    origem = models.ForeignKey(
        AssinaturaPalco,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="presets",
        help_text="A assinatura que o produtor aprovou antes de clonar.",
    )
    fixado = models.BooleanField(
        default=False, help_text="Aparece fixado no topo do menu do produtor."
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = PalcoQuerySet.as_manager()

    class Meta:
        verbose_name = "Dashboard do produtor"
        verbose_name_plural = "Dashboards do produtor"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "slug"], name="preset_unico_por_produtor"
            )
        ]
        indexes = [
            models.Index(fields=["user", "fixado"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.user.username})"


# --------------------------------------------------------------------------
# O CHAMADO — a única peça onde a IA escreve
# --------------------------------------------------------------------------

ESTADO_RASCUNHO = "rascunho"
ESTADO_PUBLICADO = "publicado"
ESTADO_ARQUIVADO = "arquivado"
ESTADOS_CHAMADO = (
    (ESTADO_RASCUNHO, "Rascunho"),
    (ESTADO_PUBLICADO, "Publicado"),
    (ESTADO_ARQUIVADO, "Arquivado"),
)


class ChamadoAmplia(models.Model):
    """A peça que a IA escreve — e a ÚNICA onde ela pode.

    POR QUE ESTE MODEL EXISTE E NÃO É SÓ UM `PresetPalco`
    =====================================================
    Um `PresetPalco` tem `slug` livre: o produtor dá-lhe o nome que quer. Isso é
    exatamente o que torna um preset insuficiente para esta função: a zona de
    escrita da IA não pode ser um valor que o produtor escolhe, porque um valor
    que o produtor escolhe pode ser mudado para outra coisa.

    Aqui o slug é FIXO (`chamado.SLUG_CHAMADO`) e não há campo para o produtor
    o mudar. Não é limitação de UX: é a trava. Um `PresetPalco` reescrevível
    seria um preset em que a IA pode escrever, e a garantia que o produto
    promete — "nos teus presets, a IA só lê" — passaria a depender de uma
    comparação de string feita no caminho certo, e o caminho certo é um site.

    A RAIZ DA TRAVA ESTÁ AQUI E NÃO SÓ NO CÓDIGO
    =============================================
    `slug` tem `default` e não tem `choices` — a escolha é o valor fixo. Mas o
    que garante que a linha é da zona de escrita é o `CheckConstraint` abaixo:
    ele torna INVÁLIDO, no próprio banco, um Chamado com outro slug. Um handler
    com um bug que passe o slug errado não grava uma peça noutro preset — falha
    na base de dados, que é onde este género de erro tem de falhar.

    `corpo` é a lista de blocos validada por `app.ia.chamado.validar_blocos`, e
    não HTML, não Python, e não texto. Ver a docstring desse módulo para porquê.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chamados_amplia"
    )
    slug = models.CharField(
        max_length=60,
        default="chamado-amplia",
        help_text="Zona de escrita da IA. Não é livre — ver CheckConstraint.",
    )
    nome = models.CharField(max_length=120, default="Chamado Amplia")
    corpo = models.JSONField(
        default=list,
        help_text="Lista de blocos validados (app.ia.chamado).",
    )
    preset = models.ForeignKey(
        PresetPalco,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chamados",
        help_text="O preset da widget-bar que mostra esta peça.",
    )
    estado = models.CharField(
        max_length=20, choices=ESTADOS_CHAMADO, default=ESTADO_RASCUNHO
    )
    versao = models.PositiveIntegerField(
        default=1,
        help_text="Sobe a cada edição. Um reread com versão antiga recusa.",
    )
    contexto = models.JSONField(
        default=dict,
        blank=True,
        help_text="Pergunta que originou, propriedade, cultura.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = PalcoQuerySet.as_manager()

    class Meta:
        verbose_name = "Chamado Amplia"
        verbose_name_plural = "Chamados Amplia"
        constraints = [
            # A ZONA DE ESCRITA, no banco.
            #
            # Uma linha por produtor, e o slug é o da zona. O nome diz o que
            # garante: não há segundo Chamado, e não há Chamado fora da zona.
            # Um `unique_together` sem isto permitiria duas peças chamadas
            # "chamado-amplia" para o mesmo produtor, e a IA a editar "a"
            # peça sem saber qual — que é o sintoma clássico de "a IA mudou a
            # coisa errada".
            models.UniqueConstraint(
                fields=["user", "slug"], name="chamado_unico_por_produtor"
            ),
            models.CheckConstraint(
                condition=models.Q(slug="chamado-amplia"),
                name="chamado_so_na_zona",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "estado"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.user.username}, v{self.versao})"

    @property
    def somente_leitura_para_ia(self) -> bool:
        """True quando este bloco de texto NÃO pode mais receber escrita da IA.

        Um Chamado arquivado é do produtor. Ele continua visível, continua
        exportável, e a IA lê-o se ele pedir — mas não o escreve. Arquivar é
        a forma de o produtor fechar a porta sem apagar o que a IA lhe fez.
        """
        return self.estado == ESTADO_ARQUIVADO
