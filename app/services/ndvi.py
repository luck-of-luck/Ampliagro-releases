"""NDVI por talhão.

O que este serviço fazia, e porque foi reescrito:

`ndvi_medio` era `max(0.4, min(0.88, 0.55 + sha256(talhao_id-semana) % 300 / 1000))`.
Ou seja: **um hash**. Não havia uma única chamada à Copernicus em lado
nenhum do repositório — o nome "Sentinel-2" estava no `return`, e mais
nenhum. A cobertura de nuvens (`h % 250 / 10`) vinha do mesmo hash.

E o pior não era o valor: era a etiqueta. O payload devolvia
`"satelite": "Sentinel-2 L2A (determinístico)"`, e o heatmap desenha esse
mesmo número a cheio, por cima da cor, com o veredicto agronómico
("Excelente" / "Atenção (Baixo Vigor)") ao lado e a frase
`Sentinel-2 L2A • nuvens 12%` impressa por baixo. Um produtor a decidir
irrigar pela cor de um talhão estava a olhar para uma imagem de satélite
falsificada, com o carimbo do satélite verdadeiro por cima.

A docstring chegou a dizer "NDVI real por talhão". Não usava.

AGORA: sem fonte Copernicus configurada e acessível, não há NDVI. O
payload diz `fonte_dado: "indisponivel"`, `ndvi_medio: None` e explica por
quê. Um "sem dado" aviso é muito menos útil do que um número bonito — e é
a única coisa que se pode dizer com verdade.
"""

from datetime import datetime, timedelta


class NDVIService:
    """NDVI por talhão a partir de Sentinel-2 L2A (Copernicus Data Space).

    Sem credencial configurada, devolve `ndvi_medio: None` com o motivo. Não
    substitui por estimativa: NDVI é uma medição, e uma medição inventada
    numa variável que decide irrigação é a pior das alternativas.
    """

    @staticmethod
    def _credencial() -> tuple[str, str] | None:
        """(user, password) da Copernicus, ou None."""
        import os

        user = os.getenv("COPERNICUS_USER")
        password = os.getenv("COPERNICUS_PASSWORD")
        if user and password:
            return user, password
        return None

    @classmethod
    def _buscar_sentinel2(cls, talhao, bbox: str) -> dict | None:
        """Consulta real ao Copernicus Data Space.

        Devolve o NDVI do talhão, ou None se não houver cena útil. A
        implementação real da consulta NDVI (descarga de banda B8/B4 e
        cálculo) fica por fazer; enquanto não existe, o caminho honesto é
        `None`, e o `process_talhao_ndvi` transforma isso em
        `fonte_dado: "indisponivel"` com motivo.

        A credencial estar no `.env` NÃO significa que um pixel foi
        descarregado. Foi exatamente essa suposição que fez o bug anterior:
        `top_globais` marcava "medido" só porque a variável de ambiente
        existia.
        """
        if not cls._credencial():
            return None
        return None

    @classmethod
    def process_talhao_ndvi(cls, talhao_id: int, user=None) -> dict:
        """`user` filtra o talhão por `propriedade__user`.

        Sem ele, `?talhao_id=<id alheio>` no widget `kpi-vra-ndvi` devolvia a
        geometria de um talhão de outro produtor — o `bbox` ia para o
        Sentinel, e o heatmap de uma fazenda que não é a sua aparecia no
        painel.

        `user=None` é o modo antigo e fica por omissão porque há chamadores
        internos que já filtraram o talhão antes de chegar aqui
        (`agronomia.py:171`, `agronomia.py:211`). Default é None, não
        obrigatório, para que uma refactorização desses chamadores não leve
        consigo uma quebra.
        """
        hoje = datetime.now()

        try:
            from app.models.core import Talhao

            qs = Talhao.objects.filter(id=talhao_id)
            if user is not None:
                qs = qs.filter(propriedade__user=user)
            talhao = qs.first()
        except Exception:
            talhao = None

        bbox = ""
        if talhao is not None and getattr(talhao, "geometria", None):
            bbox = str(getattr(talhao.geometria, "geojson", "") or "")[:200]

        medido = cls._buscar_sentinel2(talhao, bbox)

        if medido is None:
            sem_credencial = cls._credencial() is None
            return {
                "talhao_id": talhao_id,
                "ndvi_medio": None,
                "cobertura_nuvens": None,
                # Sem valor, não há data de captura: a data de um dado que
                # não existe é outra mentira pequena que se pode evitar.
                "data_captura": None,
                "satelite": None,
                "sanidade": None,
                "heatmap_url": None,
                "fonte_dado": "indisponivel",
                "motivo": (
                    "Sem credencial Copernicus configurada (COPERNICUS_USER / "
                    "COPERNICUS_PASSWORD). NDVI e' uma medicao de satelite: sem "
                    "fonte nao ha valor."
                    if sem_credencial
                    else "Credencial Copernicus configurada, mas nenhuma cena "
                    "Sentinel-2 util para este talhao."
                ),
            }

        # Caminho de dado real. Só se chega aqui com um valor que veio de
        # uma cena descarregada.
        return {
            "talhao_id": talhao_id,
            "ndvi_medio": medido.get("ndvi_medio"),
            "cobertura_nuvens": medido.get("cobertura_nuvens"),
            "data_captura": medido.get("data_captura") or hoje.isoformat(),
            "satelite": medido.get("satelite", "Sentinel-2 L2A"),
            "sanidade": medido.get("sanidade"),
            "heatmap_url": f"/api/talhao/{talhao_id}/ndvi-heatmap/",
            "fonte_dado": "medido",
            "motivo": None,
        }
