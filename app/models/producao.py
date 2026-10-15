from datetime import timedelta
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from app.validators import validate_evidencia, validate_json_safe, validate_upload_size


class RegistroProducao(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="registros_producao"
    )
    cultura = models.ForeignKey(
        # PROTECT, e nao CASCADE. Apagar uma cultura do catalogo nao pode
        # apagar a safra de ninguem: `CASCADE` levava tres anos de producao
        # registada sem um unico aviso. Com PROTECT, a operacao e' recusada e
        # quem tenta recebe a verdade — que ha registos a depender. Ver
        # `tests_cascata_cultura.py`.
        "Cultura",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    cultura_key = models.CharField(
        max_length=100,
        blank=True,
        help_text="Id do CulturesLoader (fallback quando não há FK)",
    )
    grupo = models.CharField(max_length=20, default="vegetal")
    nome = models.CharField(max_length=150)
    status = models.CharField(max_length=20, default="ativo")
    location = models.CharField(max_length=150, blank=True)
    data_registro = models.DateField(null=True, blank=True)
    quantidade = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    unidade = models.CharField(max_length=20, blank=True)
    observacoes = models.TextField(blank=True)
    fields_json = models.JSONField(default=dict, blank=True)
    treatments = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome} ({self.get_grupo_display()})"

    class Meta:
        verbose_name = "Registro de Produção"
        verbose_name_plural = "Registros de Produção"
        ordering = ["-criado_em"]


class EstagioCultura(models.Model):
    TIPO_CHOICES = [
        ("estagio", "Estágio"),
        ("sub", "Sub-estágio"),
    ]
    registro = models.ForeignKey(
        "RegistroProducao", on_delete=models.CASCADE, related_name="estagios"
    )
    estagio_pai = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="sub_estagios",
    )
    nome = models.CharField(max_length=100)
    cor = models.CharField(max_length=7, default="#6366f1")
    icone = models.CharField(max_length=50, default="bi-circle-fill")
    ordem = models.IntegerField(default=0)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default="estagio")
    concluido = models.BooleanField(default=False)
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem"]
        verbose_name = "Estágio da Cultura"
        verbose_name_plural = "Estágios da Cultura"
        indexes = [
            models.Index(fields=["registro", "ordem"]),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    def all_sub_completed(self):
        subs = self.sub_estagios.all()
        if not subs.exists():
            return self.concluido
        return all(s.concluido for s in subs)


class TarefaEstagio(models.Model):
    estagio = models.ForeignKey(
        "EstagioCultura", on_delete=models.CASCADE, related_name="tarefas"
    )
    descricao = models.TextField(blank=True)
    funcionario = models.ForeignKey(
        "Funcionario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tarefas_estagio",
    )
    cargo_alvo = models.CharField(
        max_length=30, blank=True, help_text="Cargo-alvo da tarefa"
    )
    setor = models.CharField(
        max_length=100, blank=True, help_text="Setor/departamento alvo"
    )
    concluida = models.BooleanField(default=False)
    concluida_em = models.DateTimeField(null=True, blank=True)
    # Kanban
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("andamento", "Em Andamento"),
        ("concluido", "Concluído"),
    ]
    PRIORIDADE_CHOICES = [
        ("baixa", "Baixa"),
        ("media", "Média"),
        ("alta", "Alta"),
        ("urgente", "Urgente"),
    ]
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="pendente", db_index=True
    )
    prioridade = models.CharField(
        max_length=10, choices=PRIORIDADE_CHOICES, default="media"
    )
    data_limite = models.DateField(null=True, blank=True, help_text="Prazo da tarefa")
    # Associação direta à propriedade para filtro rápido do servidor (denormalizado)
    propriedade = models.ForeignKey(
        "Propriedade",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tarefas_kanban",
        help_text="Denormalizado para kanban do servidor",
    )
    ordem = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    # Lógica de sync status/concluida e denormalização de propriedade
    # movida para app/signals.py (pre_save signal)

    class Meta:
        ordering = ["ordem"]
        verbose_name = "Tarefa do Estágio"
        verbose_name_plural = "Tarefas do Estágio"
        indexes = [
            models.Index(fields=["estagio", "status"]),
            models.Index(fields=["propriedade", "status"]),
            models.Index(fields=["cargo_alvo"]),
            models.Index(fields=["propriedade", "concluida"]),
            models.Index(fields=["funcionario", "status"]),
        ]

    def __str__(self):
        return f"{self.descricao[:50]} ({self.estagio.nome})"


class PrescricaoVRA(models.Model):
    safra = models.ForeignKey(
        "Safra", on_delete=models.CASCADE, related_name="prescricoes_vra"
    )
    talhao = models.ForeignKey(
        "Talhao", on_delete=models.CASCADE, related_name="prescricoes_vra"
    )
    # PROTECT, e nao CASCADE. Apagar uma cultura do catalogo nao pode
    # apagar a safra de ninguem: `CASCADE` levava tres anos de producao
    # registada sem um unico aviso. Com PROTECT, a operacao e' recusada e
    # quem tenta recebe a verdade — que ha registos a depender. Ver
    # `tests_cascata_cultura.py`.
    cultura = models.ForeignKey("Cultura", on_delete=models.PROTECT)
    tipo_insumo = models.CharField(
        max_length=20,
        choices=[
            ("FERTILIZANTE", "Fertilizante"),
            ("CORRETIVO", "Corretivo"),
            ("DEFENSIVO", "Defensivo"),
            ("SEMENTE", "Semente"),
        ],
    )
    insumo = models.ForeignKey(
        "Insumo", on_delete=models.SET_NULL, null=True, blank=True
    )
    dose_ha = models.DecimalField(max_digits=8, decimal_places=2)
    unidade = models.CharField(max_length=20)
    grade_geojson = models.JSONField(
        default=dict, help_text="FeatureCollection com células + dose_ha por célula"
    )
    iso_xml = models.TextField(blank=True)
    arquivo_iso = models.FileField(
        upload_to="vra_iso/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(["iso", "xml", "bin"]),
            validate_upload_size,
        ],
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    # ------------------------------------------------------------------
    # PROVENIENCIA (A2). O que a prescricao PREVIU, e com que evidencia.
    #
    # O que faltava, e porque e' o A2 da carta:
    #
    # `PrescricaoVRA` era um receituario de *escrita*. Guardava a dose que se
    # mandou aplicar, e nada mais. Nao guardava o que se esperava que a dose
    # produzisse, nem a evidencia que produziu a recomendacao, nem a versao do
    # conhecimento agronomico que estava a ser usado.
    #
    # Sem esses tres campos, `dose_ha` e' um numero sem justificacao: e' impossivel
    # responder a "porque mandou isto?" seis meses depois, e impossivel aprender
    # com o erro. E' exactamente a aposta do §4.3 da carta - **procedencia
    # auditavel por talhao e por decisao** - que e' o diferençador defensavel,
    # porque um competidor com 9 anos de dados nao versionados nao a consegue
    # retrofitar.
    #
    # O elo para o desfecho **ja existia**: `safra` aponta para `Safra`, que tem
    # `produtividade` e `data_colheita`, e `Safra` pode estarogiada num talhao. O
    # que faltava era o lado da previsao. Por isso A2 nao e' um modelo novo - e'
    # uma ligacao, e `erro_percentual` le as duas pontas.
    #
    # `produtividade_esperada` e' NULL ate haver previsao. E' deliberado: uma
    # prescricao sem previsao gravada tem de continuar a ser uma prescricao
    # valida - o produtor nao e' obrigado a adivinhar o futuro para poder semear.
    # ------------------------------------------------------------------
    produtividade_esperada = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="O que a recomendacao previa que a dose produziria, na mesma "
        "unidade de Safra.produtividade. NULL = previsao nao registada.",
    )
    contexto_recomendacao = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_evidencia],
        help_text="Evidencia que produziu a recomendacao: clima e solo medidos no "
        "momento, com o carimbo fonte_dado de cada um (medido | sem_dado | "
        "suspect). Vazio = recomendacao sem evidencia registada.",
    )
    versao_analise = models.CharField(
        max_length=60,
        blank=True,
        help_text="Versao do conhecimento agronomico que produziu a dose. Sem isto, "
        "dois anos de prescricoes sao indistinguiveis e nao se pode melhorar a "
        "calibracao.",
    )

    # ---------------------------------------------------------------
    # O ERRO MEDIDO CONTRA O DESFECHO
    #
    # Estas properties sao o produto do A2. Nao sao campos: sao a leitura das
    # duas pontas, e por isso nunca podem divergir do que esta gravado.
    #
    # Devolvem `None` quando falta uma das pontas, e NAO zero. Um erro de 0%
    # (acertou em cheio) e um erro desconhecido sao coisas completamente
    # diferentes, e um `0` nao distingue as duas - e' o `sem_dado` declarado a
    # tratar-se de `medido`.
    # ---------------------------------------------------------------
    @property
    def produtividade_realizada(self):
        """O que foi colhido, lido da safra. `None` = ainda nao colhido."""
        if self.safra_id is None:
            return None
        return self.safra.produtividade

    @property
    def erro_percentual(self):
        """Erro relativo da previsao, em %.

        Positivo = a previsao foi otimista (rendeu menos do que se previa).
        Negativo = foi pessimista.

        `None` quando falta a previsao, falta a realizada, ou a realizada e'
        zero - porque um erro relativo a zero nao tem resposta, e devolver
        `inf` ou `0` seria inventar.
        """
        realizada = self.produtividade_realizada
        esperada = self.produtividade_esperada
        if realizada is None or esperada is None:
            return None
        r = float(realizada)
        if r == 0.0:
            return None
        return round((float(esperada) - r) / r * 100.0, 2)

    @property
    def desfecho_medido(self):
        """A pergunta 'isto foi avaliado?' em vez de devolver 0 para 'nao'."""
        return (
            self.produtividade_esperada is not None
            and self.produtividade_realizada is not None
        )

    @property
    def fonte_dado_erro(self):
        """De onde vem o erro — e tem de concordar com `erro_percentual`.

        MEDIDO ao correr a primeira vez este teste: com `realizada = 0` e
        `esperada = 70`, `erro_percentual` devolvia `None` (um erro relativo a
        zero nao tem resposta) mas isto devolvia `"medido"`, porque so olhava
        para "as duas pontas existem?". As duas propriedades discordavam entre
        si — que e' exactamente a falha que o A0 e o A2 existem para impedir,
        agora dentro do meu proprio codigo.

        Sao tres estados, e o terceiro e' o que faltava:

            `medido`           as duas pontas existem e o erro calcula-se
            `medido_sem_erro`  as duas pontas existem, mas o erro nao e'
                              definivel (realizada = 0)
            `sem_dado`         falta uma das pontas

        `medido_sem_erro` e' o mesmo vocabulario de `medido_com_ressalva` que o
        `experiment.js` passou a usar. Uma produtividade de 0 e' uma medicao
        real — a lavoura falhou, ou o registo e' mesmo zero — e dizer `sem_dado`
        seria mentir sobre o que se sabe. O que nao se sabe e' o erro.
        """
        if self.produtividade_esperada is None or self.produtividade_realizada is None:
            return "sem_dado"
        if self.erro_percentual is None:
            return "medido_sem_erro"
        return "medido"

    @property
    def proveniencia(self):
        """O pacote de auditoria: o que foi recomendado, porque, e o que saiu.

        E' isto que um comprador, uma cooperativa ou um investidor pede, e que
        um concorrente com dados nao versionados nao consegue produzir.
        """
        return {
            "prescricao_id": self.pk,
            "talhao_id": self.talhao_id,
            "safra_id": self.safra_id,
            "dose_ha": float(self.dose_ha) if self.dose_ha is not None else None,
            "unidade": self.unidade,
            "produtividade_esperada": (
                float(self.produtividade_esperada)
                if self.produtividade_esperada is not None
                else None
            ),
            "produtividade_realizada": (
                float(self.produtividade_realizada)
                if self.produtividade_realizada is not None
                else None
            ),
            "erro_percentual": self.erro_percentual,
            "fonte_dado_erro": self.fonte_dado_erro,
            "versao_analise": self.versao_analise or None,
            "contexto_recomendacao": self.contexto_recomendacao or {},
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
        }

    class Meta:
        verbose_name = "Prescrição VRA"
        verbose_name_plural = "Prescrições VRA"
        indexes = [
            # A consulta do A2 e' "as prescricoes desta safra que ja foram
            # avaliadas". Um indice por safra evita varrer a tabela toda assim
            # que a base cresce.
            models.Index(fields=["safra", "talhao"]),
        ]


class ZARC(models.Model):
    cultura = models.ForeignKey(
        # PROTECT, e nao CASCADE. Apagar uma cultura do catalogo nao pode
        # apagar a safra de ninguem: `CASCADE` levava tres anos de producao
        # registada sem um unico aviso. Com PROTECT, a operacao e' recusada e
        # quem tenta recebe a verdade — que ha registos a depender. Ver
        # `tests_cascata_cultura.py`.
        "Cultura",
        on_delete=models.PROTECT,
        related_name="zarcs",
    )
    uf = models.CharField(max_length=2)
    municipio = models.CharField(max_length=100)
    data_inicio_plantio = models.DateField()
    data_fim_plantio = models.DateField()
    ciclo_dias = models.IntegerField()
    risco_climatico = models.DecimalField(max_digits=4, decimal_places=2, default=0.2)

    class Meta:
        verbose_name = "ZARC"
        verbose_name_plural = "ZARCs"
        unique_together = ("cultura", "uf", "municipio")


# ===========================================================================
# A2b — O LACO DE MEDICAO, NO SERVIDOR
# ===========================================================================
#
# O QUE FALTAVA, E POR QUE ISTO NAO E' UM EXERCICIO DE PERSISTENCIA
# -------------------------------------------------------------------
# O `app/static/js/experiment.js` grava tudo em `localStorage`. Ou seja: uma
# medicao do produtor vive no navegador da maquina dele, morre quando limpa a
# cache, e **ninguem mais a ve** — nem o comprador, nem a cooperativa, nem o
# investidor.
#
# Isso tornava o A2 (a procedencia) uma promessa. O `PrescricaoVRA` tem
# `produtividade_esperada` e `contexto_recomendacao`, mas nada os preenchia, e o
# unico sitio onde havia mediacao real estava num `localStorage`.
#
# OFFLINE-FIRST — E PORQUE ISTO NAO E' "TIRAR O LOCALSTORAGE"
# -------------------------------------------------------
# O produto promete offline completo (PWA + IndexedDB), e o produtor esta no
# talhao, sem rede. Apagar o `localStorage` seria tirar uma **promessa**.
#
# A convencao da casa ja esta feita, em `app/static/js/data-sync.js`: local
# como cache optimista, servidor como fonte de verdade, e `_pending` como a
# bandeira de "ainda nao subiu". O A2b segue essa convencao em vez de a
# substituir — `AGENTS.md`: *"Before adding a helper, search for an existing
# one."*
#
# IDEMPOTENCIA — O PROBLEMA QUE O `data-sync.js` TEM
# --------------------------------------------------
# `data-sync.js` faz `item.id ? PUT : POST`. Uma rede cai a meio do POST: o item
# continua `_pending`, o produtor volta a premir "Sincronizar", e o servidor cria
# **duplicados**. Nao ha como o servidor saber que e' o mesmo.
#
# Por isso `uid` e' gerado **no cliente** e tem constraint de unicidade: o
# servidor faz `update_or_create` por `uid`, e o mesmo push duas vezes resulta
# no mesmo registo. E' a mesma convencao de `financeiro.py:209`
# (`hash_unico = CharField(unique=True, default=uuid4)`), adaptada para o
# cliente poder ser a origem do `uid`.
#
# O RELOGIO — DUAS COLUNAS, E PORQUE
# ----------------------------------
# `registado_em` e' o relogio do **produtor**: quando ele mediu, no talhao.
# `sincronizado_em` e' o relogio do **servidor**: quando chegou.
#
# Sao coisas diferentes, e a diferenca e' informacao. Um experimento apanhado
# pela rede tres dias depois tem `registado_em` de tres dias atras — que e'
# exactamente o contexto climatico que ele mediu. Se so se guardasse a data de
# chegada, perder-se-ia a condicao em que a medicao foi feita, que e' o que
# explica o resultado.


class Experimento(models.Model):
    """Um A/B registado. O par de talhoes e o que se compara; a metrica e' o
    que se mede; `significance_level` e' a barra que se decide antes de ver os
    numeros — mudar a barra depois de ver os dados e' como se faz p-value
    قليل."""

    uid = models.CharField(max_length=64, unique=True, default=uuid4)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="experimentos"
    )
    propriedade = models.ForeignKey(
        "Propriedade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experimentos",
    )
    # NULL e' legitimo: um produtor pode experimentar sem abrir uma safra, e
    # obrigar a abrir uma seria inventar uma exigencia para ter o que registar.
    safra = models.ForeignKey(
        "Safra",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experimentos",
    )
    cultura = models.ForeignKey(
        "Cultura",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="experimentos",
    )

    nome = models.CharField(max_length=150)
    hypothesis = models.TextField(
        blank=True, help_text="O que se espera que aconteca, em portugues do produtor"
    )
    variavel = models.CharField(
        max_length=80,
        blank=True,
        help_text="O que muda entre A e B (ex.: fertilizante_npk, variedade, irrigacao)",
    )
    tratamento_a = models.JSONField(default=dict, blank=True)
    tratamento_b = models.JSONField(default=dict, blank=True)
    talhao_a = models.ForeignKey(
        "Talhao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experimentos_a",
    )
    talhao_b = models.ForeignKey(
        "Talhao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="experimentos_b",
    )

    metricas = models.JSONField(default=list, blank=True)
    significance_level = models.FloatField(
        default=0.05,
        help_text="Barra de significancia, decidida ANTES de ver os resultados.",
    )
    status = models.CharField(
        max_length=20,
        default="ativo",
        choices=[
            ("ativo", "Ativo"),
            ("concluido", "Concluído"),
            ("arquivado", "Arquivado"),
        ],
    )
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)

    contexto_inicial = models.JSONField(
        default=dict,
        blank=True,
        help_text="Clima/solo medidos no inicio, com o carimbo fonte_dado de cada campo.",
    )
    versao_analise = models.CharField(max_length=60, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Experimento"
        verbose_name_plural = "Experimentos"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["safra", "status"]),
        ]

    def __str__(self):
        return self.nome or f"Experimento {self.pk}"


class MedicaoExperimental(models.Model):
    """Uma medicao de um tratamento. E' aqui que o dado nasce para valer."""

    uid = models.CharField(max_length=64, unique=True, default=uuid4)

    experimento = models.ForeignKey(
        Experimento, on_delete=models.CASCADE, related_name="medicoes"
    )
    prescricao = models.ForeignKey(
        PrescricaoVRA,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicoes",
        help_text="A recomendacao que esta medicao esta a avaliar. E' esta ligacao "
        "que fecha o laco do §4.3: recomendacao -> medicao -> desfecho.",
    )
    tratamento = models.CharField(
        max_length=1, choices=[("A", "A"), ("B", "B")], help_text="Qual dos dois grupos"
    )
    talhao = models.ForeignKey(
        "Talhao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicoes",
    )
    dados = models.JSONField(
        default=dict,
        blank=True,
        help_text="Os numeros medidos: {produtividade: 65, custo: 1200, ...}",
    )
    contexto = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_evidencia],
        help_text="Clima/solo no momento da medicao, CADA campo com o seu "
        "fonte_dado. Sem este carimbo a medicao nao distingue 'nao havia sensor' "
        "de 'o sensor disse 24'.",
    )
    fonte_dado = models.CharField(
        max_length=20,
        default="sem_dado",
        choices=[
            ("medido", "Medido"),
            ("medido_com_ressalva", "Medido com ressalva"),
            ("suspect", "Suspeito"),
            # `declarado`: o produtor AFIRMOU, e afirmar NAO e' medir. Sem este
            # estado, ou o sistema mente marcando como `medido`, ou desvaloriza
            # o dado do produtor marcando como `sem_dado`. Ver
            # `app/validators.py`, `ESTADOS_DE_RAIZ`.
            ("declarado", "Declarado pelo produtor"),
            ("sem_dado", "Sem dado"),
        ],
        help_text=(
            "Qualidade da evidencia que acompanha a medicao. "
            "'declarado': o produtor afirmou, e afirmar NAO e' medir — uma "
            "planilha importada continua 'declarado', porque importar nao "
            "transforma uma declaracao numa medicao. "
            "'sem_dado' NAO e' 'zero': significa que nao havia sensor, e nao "
            "que o sensor disse zero."
        ),
    )

    registado_em = models.DateTimeField(
        help_text="Quando o produtor mediu — relogio do cliente, no talhao."
    )
    sincronizado_em = models.DateTimeField(
        auto_now_add=True, help_text="Quando o servidor recebeu — relogio do servidor."
    )

    class Meta:
        verbose_name = "Medição experimental"
        verbose_name_plural = "Medições experimentais"
        ordering = ["registado_em", "id"]
        indexes = [
            models.Index(fields=["experimento", "tratamento"]),
            models.Index(fields=["experimento", "registado_em"]),
        ]

    def __str__(self):
        return f"{self.experimento_id} {self.tratamento} @ {self.registado_em:%Y-%m-%d %H:%M}"
