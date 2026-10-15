"""
proativo.py — os models do Motor Proativo (BUILD 4, segunda metade).

O QUE É PROATIVIDADE, AQUI
--------------------------
O produtor nao chama a IA. O sistema observa o calendário dele cruza com o
tempo e avisa antes de o dinheiro ir embora. Na pratica isso significa:

    "Vai chover forte sexta. A aplicação de fertilizante está marcada pra
     quinta. Com 30 mm de chuva em 24 h, o produto é lavado e o produtor
     gasta duas vezes."

A segunda metade da BUILD 4 é este módulo. A primeira (a Ponte IoT) deu as
portas do mundo físico; esta dá os olhos.

O MODELO DE GOVERNANÇA, E POR QUE ELE ESTÁ NO BANCO
---------------------------------------------------
O risco que o enunciado aponta — "o LLM começa a gerar alerta em excesso" — é
real, e a defesa **não pode morar no LLM**. O LLM é a parte não confiável do
sistema: alucina, repete, e roda no navegador de um aparelho que pode estar
fora de cobertura. Se o limite de alertas dependesse dele, o limite seria
tão instável quanto a alucinação que ele deveria conter.

Por isso cada alerta nasce com um `fingerprint` — SHA-256 do (usuário, regra,
fatos) — e a contagem é feita **contando as linhas desta tabela**. Fonte única
de verdade: um contador paralelo desincroniza do primeiro bug, e um bug de
contador significa alertas duplicados, que é exatamente o que se quer evitar.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from app.models.campos import JSONFieldPortatil


class ProativoPreferencia(models.Model):
    """Consentimento e cadência do produtor. Proatividade começa DESLIGADA.

    Isto nao e burocracia: alerta nao pedido e a forma mais hostil de
    interrupção que um sistema tem. Um produtor que recebe dez notificações
    por dia que não pediu desliga as notificações — e o sistema perde a
    chance de falar nos dois casos em que realmente importava.

    E o opt-in é por.propriedade, porque quem decide se a fazenda quer
    antecedência é quem responde por ela.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="proativo_preferencias"
    )
    propriedade = models.OneToOneField(
        "Propriedade", on_delete=models.CASCADE, related_name="proativo"
    )
    ativo = models.BooleanField(default=False)
    #: 0 = calado, 1 = crítico, 2 = atenção, 3 = informativo.
    nivel_minimo = models.IntegerField(default=2)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Preferência do motor proativo"
        verbose_name_plural = "Preferências do motor proativo"

    def __str__(self):
        return (
            f"proativo {self.propriedade_id} (user {self.user_id}) ativo={self.ativo}"
        )


class IAAlertaProativo(models.Model):
    """Um aviso que o sistema deu sozinho.

    Guardar a **origem** (`regra` ou `llm`) não é vaidade: é o que permite
    responder "por que isso apareceu?" — e, mais importante, medir se o caminho
    do LLM está produzindo algo que vale o custo dele. Um motor proativo que
    ninguém audita é um motor que ninguém pode consertar.
    """

    ORIGENS = [
        ("regra", "Regra determinística"),
        ("llm", "Raciocínio do modelo local"),
    ]
    ESTADOS = [
        ("novo", "Novo"),
        ("visto", "Visto"),
        ("resolvido", "Resolvido"),
        ("ignorado", "Ignorado"),
    ]
    NIVEIS = [
        (0, "Critico"),
        (1, "Atencao"),
        (2, "Informativo"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ia_alertas_proativos"
    )
    propriedade = models.ForeignKey(
        "Propriedade",
        on_delete=models.CASCADE,
        related_name="ia_alertas_proativos",
    )
    origem = models.CharField(max_length=8, choices=ORIGENS, default="regra")
    nivel = models.IntegerField(choices=NIVEIS, default=1)
    titulo = models.CharField(max_length=120)
    mensagem = models.TextField()
    estado = models.CharField(
        max_length=12, choices=ESTADOS, default="novo", db_index=True
    )

    #: SHA-256 de (regra + fatos). É a chave do dedup: o mesmo achado não
    #: vira dois alertas, por mais que o motor "descubra" de novo. `db_index`
    #: porque a consulta de cooldown é por usuário E por dedo.
    fingerprint = models.CharField(max_length=64, db_index=True)

    #: Evidência que produziu o alerta. Sem isto o produtor recebe uma
    #: afirmação sem base e não consegue verificar nada — e alerta que não pode
    #: ser verificado é opinião.
    evidencia = JSONFieldPortatil(default=dict, blank=True)
    #: Qualquer regra aplicável e o motivo da recusa, quando houve.
    regra = models.CharField(max_length=40, blank=True)
    visto_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Alerta proativo"
        verbose_name_plural = "Alertas proativos"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["user", "-criado_em"]),
            models.Index(fields=["user", "fingerprint", "-criado_em"]),
            models.Index(fields=["propriedade", "estado"]),
        ]
        # A unicidade por (user, fingerprint) NAO é uma constraint de banco.
        #
        # Seria a solução natural, mas `UniqueConstraint` exige os campos de
        # ambos os lados, e a janela que faz sentido aqui é de 14 DIAS — o
        # mesmo risco pode voltar legítimo depois (o produtor reagiu, o tempo
        # passou, o risco reaparece com outro conteúdo).
        #
        # Uma constraint com `criado_em__gte=agora-14d` é impossível: a
        # expressão seria reavaliada a cada insert, e o valor de `agora` muda
        # dentro da própria consulta. O dedup por janela fica então no serviço
        # (`proativo.pode_emitir`), que é onde as outras camadas de governança
        # também vivem — uma decisão de governança num único lugar, não
        # espalhada entre model e serviço.

    def __str__(self):
        return f"[{self.get_nivel_display()}] {self.titulo[:50]}"

    def marcar_visto(self):
        if self.estado == "novo":
            self.estado = "visto"
            self.visto_em = timezone.now()
            self.save(update_fields=["estado", "visto_em"])


class IACenarioPendente(models.Model):
    """Um cenário esperando o LLM do navegador olhar.

    ESTE É O MODELO QUE FECHA O ABISMO ENTRE A NUVEM E O CELULAR
    ----------------------------------------------------------
    O motor determinístico roda no servidor e sabe dizer "chuva de 30 mm na
    janela de lavagem". Isso resolve o caso óbvio. Mas o produtor tambem
    pergunta coisas que nenhuma regra de chuva cobre: "esse-defense é
    urgente no fim de semana?", "essa janela de aplicação cabe antes da
    chuva?".

    Responder isso exige um modelo. E o modelo está no dispositivo do
    produtor — o Celery no servidor não alcança o WebLLM na aba. Daí a
    fila: o servidor **deixa o cenário pronto** e devolve, e o navegador
    busca quando puder.

    Por que `contexto` está pronto, em vez de os dados e a montagem ficarem
    na aba:

    * o texto que o modelo viu fica **auditável**. Se o produtor perguntar
      "por que o sistema avisou isso?", existe uma resposta exata.
    * a montagem acontece **uma vez**, no servidor, e é testável. Se cada
      aba montasse o prompt, cada aba decidiria o que é relevante, e a
      mesma previsão viraria dois prompts diferentes dependendo de quem
      perguntou.
    * a aba só executa: baixar, raciocinar, chamar a tool. Nenhuma decisão.

    O QUE FAZ ESTA FILA NÃO VIRAR UM MONTÃO

    * **Lease com timeout** (`lease_ate`). Sem ela, duas abas do mesmo
      produtor — ou a mesma aba em dois polls sobrepostos — pegam o mesmo
      cenário e o alerta sai duas vezes. A governança do alerta veria a
      segunda e suprimiria pelo dedup, mas "o sistema se defende do seu
      próprio bug" é uma frase que não deveria ser verdade numa fila.
    * **TTL** (`expira_em`). Previsão velha não é inofensiva: é
      * enganosa*. Um cenário de chuva com 30 mm feito há três dias faz o
      produtor tomar decisão por um tempo que já mudou. Vence, e some.
    * **Limite por usuário.** A fila é por produtor e o teto é baixo,
      porque o objetivo é "o produtor sabe antes de agir", não "o servidor
      tem trabalho para fazer".
    """

    SITUACOES = [
        ("pendente", "Aguardando navegador"),
        ("em_andamento", "Processando"),
        ("concluido", "Processado"),
        ("descartado", "Descartado"),
        ("expirado", "Expirado"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ia_cenarios_proativos"
    )
    propriedade = models.ForeignKey(
        "Propriedade",
        on_delete=models.CASCADE,
        related_name="ia_cenarios_proativos",
    )
    #: O prompt pronto, exatamente como o modelo vai receber.
    contexto = models.TextField()
    #: Snapshot estruturado do cenário. Serve à auditoria e ao diagnóstico:
    #: quando o produtor diz "isso aqui não era para ter vindo", dá para ver
    #: quais tarefas e quais dias entraram.
    cenario = JSONFieldPortatil(default=dict, blank=True)

    fingerprint = models.CharField(max_length=64, db_index=True)
    situacao = models.CharField(
        max_length=14, choices=SITUACOES, default="pendente", db_index=True
    )
    #: Quantas vezes o cenário foi entregue a um navegador. Serve de freio:
    #: um cenário que ninguém consegue terminar (aba que fecha no meio,
    #: navegador sem WebGPU) volta para a fila um número limitado de vezes e
    #: depois é descartado em vez de rodar em círculo para sempre.
    tentativas = models.PositiveIntegerField(default=0)
    lease_ate = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(blank=True)
    expira_em = models.DateTimeField(db_index=True)
    encerrado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Cenário proativo pendente"
        verbose_name_plural = "Cenários proativos pendentes"
        ordering = ["criado_em"]
        indexes = [
            models.Index(fields=["user", "situacao", "criado_em"]),
            models.Index(fields=["situacao", "expira_em"]),
        ]

    def __str__(self):
        return f"cenario {self.pk} (user {self.user_id}) {self.situacao}"

    @property
    def lease_vencido(self):
        """O lease expirou? A aba que pegou não devolveu.

        `None` significa "sem lease", que também está vencido: um cenário
        nunca entregue está livre por definição.
        """
        if self.lease_ate is None:
            return True
        return self.lease_ate <= timezone.now()

    @property
    def disponivel(self):
        """Pode ser entregue agora?"""
        if self.situacao not in ("pendente", "em_andamento"):
            return False
        if self.expira_em <= timezone.now():
            return False
        if self.situacao == "em_andamento":
            return self.lease_vencido
        return True

    def marcar_concluido(self, situacao="concluido", erro=""):
        self.situacao = situacao
        self.encerrado_em = timezone.now()
        self.lease_ate = None
        if erro:
            self.ultimo_erro = erro[:2000]
        self.save(
            update_fields=[
                "situacao",
                "encerrado_em",
                "lease_ate",
                "ultimo_erro",
            ]
        )
