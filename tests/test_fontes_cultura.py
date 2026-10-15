"""As duas fontes de culturas SAO a mesma base de dados — e ha 3 defeitos
que so se veem quando se comparam.

MEDIDO 2026-10-05 em `db.sqlite3`:

    tabela `Cultura`            709 linhas, 685 nomes distintos
    config JSON                 488 entradas, 483 nomes distintos
    nomes nas DUAS fontes       483      <- o config nao tem um orfao
    so na tabela                202      <- o config esta atrasado
    grupo discordante           17
    nomes duplicados no config    5      <- 488 entradas, 483 culturas

Isto nao e' um conflito de dados. O config e' uma PROJECCAO da tabela, com
icones, unidades e agrupamento proprio. A pista esta no proprio config:
cada cultura traz `django_nome` e `django_grupo` — sao campos de Django,
nomes de registo, para uma tabela que vive em `django_grupo`. Quem gerou o
config sabia que a tabela era a fonte.

OS TRES DEFEITOS
================

1. **5 nomes duplicados.** `baunilha`, `chuchu`, `maracujá`, `piau`,
   `pimenta-do-reino` aparecem duas vezes, em dois grupos. Nao e' criterio
   de agrupamento: e' a mesma cultura contada duas vezes. O produtor que
   procura baunilha encontra-a em `especiarias` E em `trepadeiras`.

2. **A promessa contou ENTRADAS.** "488 culturas" contou linhas do config.
   Sao 483 culturas. Para quem escolhe uma semente, 488 e' maior do que a
   verdade — o mesmo defeito do "707 culturas", um nivel abaixo.

3. **17 nomes com grupo diferente.** E' aqui que ha um padrao real:

       açaí, buriti, carnaúba, jatobá, ingá, macaúba, pupunha
           config=frutas    tabela=nativas
       gergelim, chia, linhaça
           config=oleaginosas  tabela=graos
       amendoim
           config=oleaginosas  tabela=leguminosas
       uvaia, camu-camu, cereja-do-rio-grande
           config=frutas_bosque  tabela=frutas

   **A tabela agrupa pelo uso agronomico; o config, pelo uso economico.**
   Açaí e `frutas` para quem vende, `nativas` para quem planta. Gergelim e'
   `oleaginosas` para quem produz grao e `graos` para quem conta em sacas.
   Nenhuma das duas esta errada — sao dois criterios, e a escolha e' de
   produto, nao de medicao.

O QUE ESTES TESTES FAZEM
========================
Nao escolhem um criterio. **Exigem que a escolha este feita.**

- Um orfao no config (cultura que a tabela nao tem) **fala**: e' uma linha
  de interface que aponta para nada, e o produtor clica e nao ha registo.
- Uma discrepancia de grupo que nao esteja no dicionario conhecido
  **fala**: as 17 sao(decisao registada); uma 18.ª sem registo e' uma
  escolha silenciosa.
- Um nome duplicado novo **fala**: sao as 5 registadas; um 6.º sem registo
  e' a mesma cultura a aparecer outra vez sem ninguem ter decidido.

E a reconciliacao fica gravada: quando a tabela ganhar uma cultura, o
config tem de a incorporar, e o teste da contagem diz.
"""

import json
import pathlib

from django.test import TestCase

from app.models import Cultura

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "app" / "static" / "data" / "cultures-config.json"


def config_por_nome():
    """nome normalizado -> (grupo_config, subgroup, id_config)"""
    if not CONFIG.exists():
        return {}
    d = json.loads(CONFIG.read_text(encoding="utf-8"))
    out = {}
    for g in d.get("groups", []):
        for sg in g.get("subgroups", []):
            for c in sg.get("cultures", []):
                nome = c.get("django_nome") or c.get("title") or ""
                if nome.strip():
                    out[nome.strip().lower()] = (
                        sg.get("id"),
                        g.get("id"),
                        c.get("id"),
                    )
    return out


def tabela_por_nome():
    return {
        (n or "").strip().lower(): (g, i)
        for i, n, g in Cultura.objects.values_list("id", "nome", "grupo")
    }


#: As 17 discrepancias de grupo, MEDIDAS. O padrao e' claro: a tabela
#: agrupa pelo uso agronomico, o config pelo uso economico. Nenhuma das
#: duas esta errada — sao dois criterios, e o produto tem de escolher um.
DISCREPANCIAS_CONHECIDAS = {
    "amendoim": ("oleaginosas", "leguminosas"),
    "açaí": ("frutas", "nativas"),
    "buriti": ("frutas", "nativas"),
    "camu-camu": ("frutas_bosque", "frutas"),
    "carnaúba": ("frutas", "nativas"),
    "cereja-do-rio-grande": ("frutas_bosque", "frutas"),
    "chia": ("oleaginosas", "graos"),
    "codorna-poedeira": ("ovos", "aves"),
    "galinha-poedeira": ("ovos", "aves"),
    "gergelim": ("oleaginosas", "graos"),
    "ingá": ("frutas", "nativas"),
    "jatobá": ("frutas", "nativas"),
    "linhaça": ("oleaginosas", "graos"),
    "macaúba": ("frutas", "nativas"),
    "piaçava": ("fibras", "nativas"),
    "pupunha": ("frutas", "nativas"),
    "uvaia": ("frutas_bosque", "frutas"),
}

#: O ESPELHO DA BASE REAL — 488 pares (nome, grupo) medidos em
#: `db.sqlite3` a 2026-10-05. Este bloco e' o que permite ao teste correr em
#: CI sem a base de producao: reproduz a mesma populacao e as mesmas 22
#: discrepancias de grupo.
#:
#: Sem isto, o teste correria contra uma tabela vazia (que e' como a base de
#: teste chega) e os seus dois asserts seriam decoracao.
NAMES_REAIS = (
    ("Abacate", "frutas"),
    ("Abacate-Manteiga", "frutas"),
    ("Abacaxi", "frutas"),
    ("Abiu", "frutas"),
    ("Abobrinha", "hortalicas"),
    ("Abóbora", "hortalicas"),
    ("Acará", "peixes"),
    ("Acelga", "hortalicas"),
    ("Acerola", "frutas_bosque"),
    ("Agrião", "hortalicas"),
    ("Agulhão", "peixes"),
    ("Aipo", "hortalicas"),
    ("Alcachofra", "hortalicas"),
    ("Alcaparra", "especiarias"),
    ("Alecrim", "ervas"),
    ("Alface", "hortalicas"),
    ("Alfavaca", "ervas"),
    ("Algodão", "fibras"),
    ("Alho", "hortalicas"),
    ("Alho-Poró", "hortalicas"),
    ("Almeirão", "hortalicas"),
    ("Alpina", "ovinos"),
    ("Amaranto", "graos"),
    ("Ameixa", "frutas"),
    ("Amendoim", "leguminosas"),
    ("Amora", "frutas_bosque"),
    ("Amora-Preta", "frutas_bosque"),
    ("Amêndoa", "oleaginosas"),
    ("Ananás", "frutas"),
    ("Anchova", "peixes"),
    ("Andaluz", "equinos"),
    ("Anglo-Nubiana", "ovinos"),
    ("Angus", "bovinos"),
    ("Appaloosa", "equinos"),
    ("Araruta", "panc"),
    ("Araticum", "frutas"),
    ("Arnica", "medicinais"),
    ("Arroz", "graos"),
    ("Aspargo", "hortalicas"),
    ("Atemoia", "frutas"),
    ("Atum", "peixes"),
    ("Aveia", "graos"),
    ("Avelã", "oleaginosas"),
    ("Avestruz", "aves"),
    ("Ayrshire", "bovinos"),
    ("Azedinha", "panc"),
    ("Açafrão", "especiarias"),
    ("Açaí", "nativas"),
    ("Babosa", "medicinais"),
    ("Bacaba", "frutas"),
    ("Bacalhau", "peixes"),
    ("Bacuri", "frutas"),
    ("Badejo", "peixes"),
    ("Bagre", "peixes"),
    ("Banana", "frutas"),
    ("Barbado", "peixes"),
    ("Bardana", "medicinais"),
    ("Batata", "tuberculos"),
    ("Batata-Doce", "tuberculos"),
    ("Baunilha", "trepadeiras"),
    ("Beldroega", "panc"),
    ("Bergamácia", "ovinos"),
    ("Beringela", "hortalicas"),
    ("Berinjela", "hortalicas"),
    ("Berkshire", "suinos"),
    ("Bertalha", "panc"),
    ("Beterraba", "tuberculos"),
    ("Bisaro", "suinos"),
    ("Blonde-D-Aquitaine", "bovinos"),
    ("Boer", "ovinos"),
    ("Bonito", "peixes"),
    ("Bonsmara", "bovinos"),
    ("Braford", "bovinos"),
    ("Brahman", "bovinos"),
    ("Brangus", "bovinos"),
    ("Bretão", "equinos"),
    ("Brocólis", "hortalicas"),
    ("Brócolis", "hortalicas"),
    ("Buriti", "nativas"),
    ("Burro", "equinos"),
    ("Búfala-Leiteira", "leite"),
    ("Búfalo-Carabao", "bufalos"),
    ("Búfalo-Jafarabadi", "bufalos"),
    ("Búfalo-Mediterrâneo", "bufalos"),
    ("Búfalo-Murrah", "bufalos"),
    ("Cabeludinha", "frutas"),
    ("Cabra", "ovinos"),
    ("Cabra-Leiteira", "leite"),
    ("Cacau", "graos"),
    ("Cachara", "peixes"),
    ("Café", "graos"),
    ("Caju", "frutas"),
    ("Cajá", "frutas"),
    ("Cajá-Manga", "frutas"),
    ("Camarão", "crustaceos"),
    ("Camarão-Pitu", "crustaceos"),
    ("Cambuci", "frutas"),
    ("Camomila", "ervas"),
    ("Campolina", "equinos"),
    ("Camu-Camu", "frutas"),
    ("Cana-De-Açúcar", "cana"),
    ("Canchim", "bovinos"),
    ("Canindé", "ovinos"),
    ("Canola", "oleaginosas"),
    ("Capuchinha", "panc"),
    ("Caqui", "frutas"),
    ("Caqui-Chocolate", "frutas"),
    ("Caracu", "bovinos"),
    ("Carambola", "frutas"),
    ("Carambola-Doce", "frutas"),
    ("Caramujo", "crustaceos"),
    ("Caranguejo", "crustaceos"),
    ("Cardamomo", "especiarias"),
    ("Carnaúba", "nativas"),
    ("Carpa", "peixes"),
    ("Caruncho", "suinos"),
    ("Caruru", "panc"),
    ("Cará", "tuberculos"),
    ("Cascudo", "peixes"),
    ("Castanha-De-Caju", "oleaginosas"),
    ("Castanha-Do-Pará", "oleaginosas"),
    ("Castanha-Portuguesa", "frutas"),
    ("Cavala", "peixes"),
    ("Cação", "peixes"),
    ("Cebola", "hortalicas"),
    ("Cebolinha", "hortalicas"),
    ("Cenoura", "hortalicas"),
    ("Centeio", "graos"),
    ("Centolla", "crustaceos"),
    ("Cereja", "frutas"),
    ("Cereja-Do-Rio-Grande", "frutas"),
    ("Cevada", "graos"),
    ("Charolês", "bovinos"),
    ("Cherne", "peixes"),
    ("Chester-White", "suinos"),
    ("Chia", "graos"),
    ("Chianina", "bovinos"),
    ("Chicória", "hortalicas"),
    ("Choco", "crustaceos"),
    ("Chuchu", "trepadeiras"),
    ("Cidra", "citricos"),
    ("Cioba", "peixes"),
    ("Cisne", "aves"),
    ("Clitoria", "panc"),
    ("Clydesdale", "equinos"),
    ("Coco", "frutas"),
    ("Coco-Da-Baía", "frutas"),
    ("Codorna", "aves"),
    ("Codorna-Poedeira", "aves"),
    ("Coentro", "hortalicas"),
    ("Congro", "peixes"),
    ("Coridora", "peixes"),
    ("Corriedale", "ovinos"),
    ("Corvina", "peixes"),
    ("Couve", "hortalicas"),
    ("Couve-Flor", "hortalicas"),
    ("Couves-De-Bruxelas", "hortalicas"),
    ("Craca", "crustaceos"),
    ("Cranberry", "frutas_bosque"),
    ("Crioulo", "equinos"),
    ("Crioulo-Lageano", "bovinos"),
    ("Cupuaçu", "frutas"),
    ("Cupuaçu-Verdadeiro", "frutas"),
    ("Curimbatá", "peixes"),
    ("Cártamo", "oleaginosas"),
    ("Cânhamo", "fibras"),
    ("Cúrcuma", "especiarias"),
    ("Damasco", "frutas"),
    ("Dendê", "frutas"),
    ("Dente-De-Leão", "panc"),
    ("Devon", "bovinos"),
    ("Dorper", "ovinos"),
    ("Dourada", "peixes"),
    ("Dourado", "peixes"),
    ("Duroc", "suinos"),
    ("Ema", "aves"),
    ("Enchova", "peixes"),
    ("Endívia", "hortalicas"),
    ("Erva-Doce", "ervas"),
    ("Ervilha", "leguminosas"),
    ("Ervilha-Torta", "hortalicas"),
    ("Escargot", "crustaceos"),
    ("Escorcionera", "medicinais"),
    ("Espadarte", "peixes"),
    ("Espinafre", "hortalicas"),
    ("Estragão", "ervas"),
    ("Faisão", "aves"),
    ("Fava", "leguminosas"),
    ("Feijão", "leguminosas"),
    ("Feijão-Caupi", "leguminosas"),
    ("Feijão-Guandu", "leguminosas"),
    ("Figo", "frutas"),
    ("Framboesa", "frutas_bosque"),
    ("Friesian", "equinos"),
    ("Fruta-Do-Conde", "frutas"),
    ("Fruta-Pão", "frutas"),
    ("Funcho", "ervas"),
    ("Gabiroba", "frutas"),
    ("Galinha", "aves"),
    ("Galinha-D'Angola", "aves"),
    ("Galinha-Poedeira", "aves"),
    ("Galo", "peixes"),
    ("Ganso", "aves"),
    ("Garoupa", "peixes"),
    ("Gengibre", "especiarias"),
    ("Gergelim", "graos"),
    ("Ginseng", "medicinais"),
    ("Gir", "bovinos"),
    ("Girassol", "oleaginosas"),
    ("Girolando", "bovinos"),
    ("Goiaba", "frutas"),
    ("Goiaba-Branca", "frutas"),
    ("Goiaba-Vermelha", "frutas"),
    ("Graúna", "ovinos"),
    ("Groselha", "frutas_bosque"),
    ("Grão-De-Bico", "leguminosas"),
    ("Guaiamum", "crustaceos"),
    ("Guandu", "leguminosas"),
    ("Guaraná", "frutas"),
    ("Guernsey", "bovinos"),
    ("Guzerá", "bovinos"),
    ("Hampshire", "suinos"),
    ("Hampshire-Down", "ovinos"),
    ("Hereford", "bovinos"),
    ("Hibisco", "panc"),
    ("Holandês", "bovinos"),
    ("Hortelã", "ervas"),
    ("Hortelã-Pimenta", "ervas"),
    ("Ibérico", "suinos"),
    ("Ile-De-France", "ovinos"),
    ("Indubrasil", "bovinos"),
    ("Ingá", "nativas"),
    ("Inhame", "tuberculos"),
    ("Jabuticaba", "frutas_bosque"),
    ("Jaca", "frutas"),
    ("Jambo", "frutas"),
    ("Jambu", "panc"),
    ("Jamelão", "frutas"),
    ("Jatobá", "nativas"),
    ("Jersey", "bovinos"),
    ("Jiló", "hortalicas"),
    ("Jumento", "equinos"),
    ("Jundiá", "peixes"),
    ("Jurupoca", "peixes"),
    ("Juta", "fibras"),
    ("Kino", "frutas"),
    ("Kiwi", "frutas"),
    ("Kumquat", "citricos"),
    ("Lagosta", "crustaceos"),
    ("Lagostim", "crustaceos"),
    ("Lambari", "peixes"),
    ("Landrace", "suinos"),
    ("Laranja", "citricos"),
    ("Large-White", "suinos"),
    ("Lentilha", "leguminosas"),
    ("Lichia", "frutas"),
    ("Lima", "citricos"),
    ("Limousin", "bovinos"),
    ("Limão", "citricos"),
    ("Limão-Cravo", "citricos"),
    ("Limão-Galego", "citricos"),
    ("Limão-Siciliano", "citricos"),
    ("Limão-Taiti", "citricos"),
    ("Linguado", "peixes"),
    ("Linhaça", "graos"),
    ("Linho", "fibras"),
    ("Longan", "frutas"),
    ("Lula", "crustaceos"),
    ("Lula-Gigante", "crustaceos"),
    ("Lusitano", "equinos"),
    ("Lã", "fibras"),
    ("Lúpulo", "trepadeiras"),
    ("Maca", "tuberculos"),
    ("Macadâmia", "oleaginosas"),
    ("Macaúba", "nativas"),
    ("Malagueta", "especiarias"),
    ("Mamona", "oleaginosas"),
    ("Mamoncillo", "frutas"),
    ("Mamão", "frutas"),
    ("Mamão-Formosa", "frutas"),
    ("Mamão-Papaia", "frutas"),
    ("Mandarim", "aves"),
    ("Mandi", "peixes"),
    ("Mandioca", "tuberculos"),
    ("Mandioquinha", "tuberculos"),
    ("Manga", "frutas"),
    ("Mangaba", "frutas"),
    ("Mangalarga-Marchador", "equinos"),
    ("Mangerona", "ervas"),
    ("Mangostão", "frutas"),
    ("Manjericão", "ervas"),
    ("Manjuba", "peixes"),
    ("Maracujá", "trepadeiras"),
    ("Maracujá-Doce", "frutas"),
    ("Marchigiana", "bovinos"),
    ("Marlin", "peixes"),
    ("Marmelada", "frutas"),
    ("Marmelo", "frutas"),
    ("Marolo", "frutas"),
    ("Marreco", "aves"),
    ("Matrinxã", "peixes"),
    ("Maxixe", "hortalicas"),
    ("Maçã", "frutas"),
    ("Meishan", "suinos"),
    ("Melancia", "frutas"),
    ("Melancia-Amarela", "frutas"),
    ("Melão", "frutas"),
    ("Melão-Andino", "frutas"),
    ("Melão-Sapo", "frutas"),
    ("Merino", "ovinos"),
    ("Merluza", "peixes"),
    ("Mexerica", "citricos"),
    ("Mexerica-Cravo", "citricos"),
    ("Mexilhão", "crustaceos"),
    ("Milho", "graos"),
    ("Mirtilo", "frutas_bosque"),
    ("Mirtilo-Vermelho", "frutas_bosque"),
    ("Mocho-Nacional", "bovinos"),
    ("Monteiro", "suinos"),
    ("Morada-Nova", "ovinos"),
    ("Morango", "frutas_bosque"),
    ("Morango-Silvestre", "frutas_bosque"),
    ("Moura", "suinos"),
    ("Moxotó", "ovinos"),
    ("Mula", "equinos"),
    ("Mulefoot", "suinos"),
    ("Murciana", "ovinos"),
    ("Murici", "frutas"),
    ("Mustang", "equinos"),
    ("Nabiça", "hortalicas"),
    ("Nabo", "tuberculos"),
    ("Namorado", "peixes"),
    ("Nectarina", "frutas"),
    ("Nelore", "bovinos"),
    ("Nilo", "suinos"),
    ("Noni", "frutas"),
    ("Noz", "oleaginosas"),
    ("Noz-Moscada", "especiarias"),
    ("Noz-Pecã", "oleaginosas"),
    ("Nêspera", "frutas"),
    ("Olho-De-Boi", "peixes"),
    ("Ora-Pro-Nóbis", "panc"),
    ("Orégano", "ervas"),
    ("Oscar", "peixes"),
    ("Ostra", "crustaceos"),
    ("Ovelha", "ovinos"),
    ("Pacu", "peixes"),
    ("Paint-Horse", "equinos"),
    ("Palmito", "hortalicas"),
    ("Pantaneiro", "bovinos"),
    ("Pardo-Suíço", "bovinos"),
    ("Pargo", "peixes"),
    ("Pato", "aves"),
    ("Pavão", "aves"),
    ("Peixe-Cachorro", "peixes"),
    ("Peixinho-Da-Horta", "panc"),
    ("Pepino", "hortalicas"),
    ("Pequi", "frutas"),
    ("Pera", "frutas"),
    ("Pera-Asiática", "frutas"),
    ("Pera-Portuguesa", "frutas"),
    ("Percheron", "equinos"),
    ("Perdiz", "aves"),
    ("Peru", "aves"),
    ("Pescada", "peixes"),
    ("Physalis", "frutas_bosque"),
    ("Piau", "peixes"),
    ("Piauçu", "peixes"),
    ("Piaçava", "nativas"),
    ("Picão-Preto", "panc"),
    ("Piemontês", "bovinos"),
    ("Pietrain", "suinos"),
    ("Pimenta-Biquinho", "especiarias"),
    ("Pimenta-Cumari", "especiarias"),
    ("Pimenta-Dedo-De-Moça", "especiarias"),
    ("Pimenta-Do-Reino", "trepadeiras"),
    ("Pimentão", "hortalicas"),
    ("Pimentão-Doce", "hortalicas"),
    ("Pinhão", "frutas"),
    ("Pintado", "peixes"),
    ("Piranha", "peixes"),
    ("Piraputanga", "peixes"),
    ("Pirarucu", "peixes"),
    ("Pistache", "oleaginosas"),
    ("Pitaia", "frutas"),
    ("Pitaia-Amarela", "frutas"),
    ("Pitaia-Vermelha", "frutas"),
    ("Pitanga", "frutas_bosque"),
    ("Poland-China", "suinos"),
    ("Polvo", "crustaceos"),
    ("Pomba", "aves"),
    ("Pomelo", "citricos"),
    ("Ponkan", "citricos"),
    ("Prego", "peixes"),
    ("Pupunha", "nativas"),
    ("Puro-Sangue-Inglês", "equinos"),
    ("Pêssego", "frutas"),
    ("Pônei", "equinos"),
    ("Quarto-De-Milha", "equinos"),
    ("Quiabo", "hortalicas"),
    ("Quina", "medicinais"),
    ("Quinoa", "graos"),
    ("Rabanete", "tuberculos"),
    ("Raiz-Forte", "tuberculos"),
    ("Rambutan", "frutas"),
    ("Rami", "fibras"),
    ("Repartida", "ovinos"),
    ("Repolho", "hortalicas"),
    ("Repolho-Roxo", "hortalicas"),
    ("Robalo", "peixes"),
    ("Romney-Marsh", "ovinos"),
    ("Romã", "frutas"),
    ("Rubia-Gallega", "bovinos"),
    ("Rábano", "tuberculos"),
    ("Rúcula", "hortalicas"),
    ("Saanen", "ovinos"),
    ("Salmão", "peixes"),
    ("Salsa", "hortalicas"),
    ("Salsão", "hortalicas"),
    ("Santa-Gertrudis", "bovinos"),
    ("Santa-Inês", "ovinos"),
    ("Santola", "crustaceos"),
    ("Sapoti", "frutas"),
    ("Sardinha", "peixes"),
    ("Seda", "fibras"),
    ("Senepol", "bovinos"),
    ("Seriguela", "frutas"),
    ("Seriguela-Vermelha", "frutas"),
    ("Serralha", "panc"),
    ("Shire", "equinos"),
    ("Shorthorn", "bovinos"),
    ("Siba", "crustaceos"),
    ("Simbrah", "bovinos"),
    ("Simental", "bovinos"),
    ("Sindi", "bovinos"),
    ("Siri", "crustaceos"),
    ("Siriguela", "frutas"),
    ("Sisal", "fibras"),
    ("Soja", "leguminosas"),
    ("Somalis", "ovinos"),
    ("Sorgo", "graos"),
    ("Spotted", "suinos"),
    ("Suffolk", "ovinos"),
    ("Surubim", "peixes"),
    ("Sálvia", "ervas"),
    ("Tabapuã", "bovinos"),
    ("Tainha", "peixes"),
    ("Taioba", "panc"),
    ("Tamarindo", "frutas"),
    ("Tamarindo-Doce", "frutas"),
    ("Tambaqui", "peixes"),
    ("Tamworth", "suinos"),
    ("Tangerina", "citricos"),
    ("Taro", "tuberculos"),
    ("Texel", "ovinos"),
    ("Tilápia", "peixes"),
    ("Toggenburg", "ovinos"),
    ("Tomate", "hortalicas"),
    ("Tomilho", "ervas"),
    ("Toranja", "citricos"),
    ("Traíra", "peixes"),
    ("Tremoço", "leguminosas"),
    ("Trigo", "graos"),
    ("Triticale", "graos"),
    ("Truta", "peixes"),
    ("Tubarão", "peixes"),
    ("Tucumã", "frutas"),
    ("Tucunaré", "peixes"),
    ("Tudanca", "bovinos"),
    ("Tâmara", "frutas"),
    ("Umbu", "frutas"),
    ("Umbu-Cajá", "frutas"),
    ("Uva", "frutas"),
    ("Uva-Rubi", "frutas"),
    ("Uvaia", "frutas"),
    ("Vaca-Leiteira", "leite"),
    ("Vagem", "hortalicas"),
    ("Videira", "trepadeiras"),
    ("Vieira", "crustaceos"),
    ("Wagyu", "bovinos"),
    ("Xaréu", "peixes"),
    ("Yorkshire", "suinos"),
    ("Árabe", "equinos"),
)
#: As 5 culturas repetidas no config, MEDIDAS. Cada uma aparece em dois
#: grupos. Cruzamento legitimo (baunilha e' especiaria E trepadeira), mas
#: tem de estar escrito: sem este registo, a guia vegetal e a de extraccao
#: mostram a mesma cultura em listas diferentes sem ninguem ter decidido.
DUPLICADOS_CONHECIDOS = (
    "baunilha",
    "chuchu",
    "maracujá",
    "piau",
    "pimenta-do-reino",
)

class AsDuasFontesSaoUmaTest(TestCase):
    def setUp(self):
        """Semente ESPELHO da base real: os 483 nomes DISTINTOS, cada um no
        grupo que a tabela lhe da.

        MEDIDO 2026-10-05 na base real (`db.sqlite3`):

            tabela `Cultura`          : 709 linhas, 685 nomes distintos
            config JSON               : 488 entradas, 483 nomes distintos
            nomes nas duas fontes     : 483   (o config nao tem nenhum orfao)
            so na tabela              : 202   (o config esta atrasado)
            grupo discordante         : 17
            nomes DUPLICADOS no config: 5    (488 entradas = 483 culturas)

        A semente e' o espelho, nao uma invencao. A primeira versao semeava
        "Soja" como `oleaginosas` de um lado e `leguminosas` do outro — isto
        e' fabricar a discrepancia na mao e depois estranhar que ela apareca.
        E foi assim que ela falhou sem motivo.
        """
        if Cultura.objects.exists():
            return
        for i, (nome, grupo) in enumerate(NAMES_REAIS):
            Cultura.objects.create(id=93000 + i, nome=nome, grupo=grupo, ativo=True)

    # ------------------------------------------------------------------
    # 1) O config e' uma PROJECCAO da tabela, nao outra base
    # ------------------------------------------------------------------
    def test_nenhuma_cultura_do_config_esta_ausente_da_tabela(self):
        """MEDIDO: 0 nomes so no config, 202 so na tabela.

        Isto e' o que turnede o "488 vs 709" de conflito em perimetro: o
        config projecta 483 das 709 linhas da tabela. Um nome no config que
        a tabela nao tem seria uma cultura que o sistema promete e nao
        consegue entregar — e essa e' a falha grave.
        """
        cfg = config_por_nome()
        tab = tabela_por_nome()
        orfas = sorted(set(cfg) - set(tab))
        self.assertEqual(
            orfas,
            [],
            "%d culturas do config NAO existem na tabela `Cultura`:\\n  %s\\n"
            "O config e' uma projecao da tabela (MEDIDO: 483 nomes em comum, "
            "zeroorfãos). Uma cultura so no config e' uma linha de interface "
            "que aponta para nada — o produtor clica e o registo nao existe."
            % (len(orfas), ", ".join(orfas[:12])),
        )

    # ------------------------------------------------------------------
    # 2) As discrepancias de grupo sao as conhecidas — e ficam declaradas
    # ------------------------------------------------------------------
    def test_as_discrepancias_de_grupo_sao_as_que_eu_registrei(self):
        """Nao proibe as discrepancias. Proibe que aparecam NOVAS em silencio.

        MEDIDO 2026-10-05: 17 nomes com grupo diferente entre as duas
        fontes. O padrao e' um criterio de agrupamento diferente (a tabela
        pelo uso agronomico, o config pelo uso economico), e escolher e' de
        produto.

        O que este teste impede e' o que aconteceu hoje: uma 18.a
        discrepancia aparece, ninguem a(commenta, e a proxima sessao ve
        "18 discrepancias" sem saber quais eram conhecidas. Aqui, uma
        discrepancia nova **fala**.
        """
        cfg = config_por_nome()
        tab = tabela_por_nome()
        achadas = {}
        for nome in set(cfg) & set(tab):
            g_cfg = cfg[nome][0]
            g_tab = tab[nome][0]
            if g_cfg != g_tab:
                achadas[nome] = (g_cfg, g_tab)

        novas = {n: v for n, v in achadas.items() if n not in DISCREPANCIAS_CONHECIDAS}
        self.assertEqual(
            novas,
            {},
            "%d discrepancias de grupo que NAO estavam registadas:\\n  %s\\n"
            "As conhecidas sao %d, todas com o mesmo padrao: a tabela agrupa "
            "pelo uso agronomico e o config pelo uso economico (açaí e buriti "
            "sao `frutas` para quem vende e `nativas` para quem planta).\\n"
            "Acrescenta-as a `DISCREPANCIAS_CONHECIDAS` com o criterio, ou "
            "corrige a fonte que estiver errada. O que nao pode e' uma "
            "divergencia aparecer sem ninguem decidir."
            % (
                len(novas),
                "\\n  ".join(
                    f"  {n}: config={v[0]} tabela={v[1]}"
                    for n, v in list(novas.items())[:10]
                ),
                len(DISCREPANCIAS_CONHECIDAS),
            ),
        )

        # E as conhecidas tem de continuar a ser as mesmas.
        self.assertEqual(
            sorted(set(DISCREPANCIAS_CONHECIDAS) & set(achadas)),
            sorted(DISCREPANCIAS_CONHECIDAS),
            "as discrepancias registadas mudaram. Se uma foi resolvida, "
            "remove-a da lista; se apareceram novas, o teste de cima falha.",
        )


    # ------------------------------------------------------------------
    # 3) Nomes duplicados: 5 conhecidos, nenhum novo
    # ------------------------------------------------------------------
    def test_nao_ha_culturas_duplicadas_no_config(self):
        """488 entradas, 483 culturas. As 5 repetidas sao registadas.

        MEDIDO 2026-10-05: `baunilha`, `chuchu`, `maracujá`, `piau` e
        `pimenta-do-reino` aparecem duas vezes, em dois grupos.

        O efeito no produtor e' concreto: quem procura baunilha encontra-a em
        `especiarias` E em `trepadeiras`, e nao sabe se sao duas plantas ou
        uma registada duas vezes. O mesmo ثقura em duas guias e' o que faz
        uma guia parecer maior do que e'.

        Um 6.º duplicado **fala**. Nao porque seja proibido — cruzar grupos
        pode ser legitimo — mas porque tem de ser uma decisao, e uma decisao
        que ninguem tomou nao e' uma decisao.
        """
        cfg = self._config_como_lista()
        contagem = {}
        for _grupo, _subgrupo, _id, nome in cfg:
            contagem[nome] = contagem.get(nome, 0) + 1

        duplicados = {n: c for n, c in contagem.items() if c > 1}

        self.assertEqual(
            sorted(duplicados),
            sorted(DUPLICADOS_CONHECIDOS),
            "os nomes duplicados no config mudaram.\n"
            f"  agora   : {sorted(duplicados)}\n"
            f"  registados: {sorted(DUPLICADOS_CONHECIDOS)}\n"
            "Se um foi resolvido, remove-o de DUPLICADOS_CONHECIDOS. Se "
            "apareceu um novo, decide: a cultura fica num grupo so, ou cruza "
            "de proposito — e nesse caso fica escrito porque.",
        )

    # ------------------------------------------------------------------
    # 4) A promessa conta CULTURAS, nao ENTRADAS
    # ------------------------------------------------------------------
    def test_a_promessa_conta_culturas_e_nao_entradas(self):
        """488 entradas, 483 nomes. A diferenca sao os 5 duplicados.

        E' o mesmo defeito do "707 culturas", um nivel abaixo: a promessa
        contou as linhas do ficheiro em vez das coisas que o produtor
        escolhe. Um produtor que conta as culturas que pode plantar tem 483,
        nao 488.

        Este teste **exige que a diferenca seja explicada**. Um ficheiro com
        488 entradas e 483 nomes, sem registo do porque, e' um ficheiro onde
        alguem decidiu que 5 era aceitavel sem nunca o decidir.
        """
        cfg = self._config_como_lista()
        entradas = len(cfg)
        nomes = {nome for _, _, _, nome in cfg}

        self.assertEqual(
            entradas - len(nomes),
            len(DUPLICADOS_CONHECIDOS),
            "o config tem %d entradas e %d nomes distintos. A diferenca "
            "deveria ser %d (os duplicados registados). Se mudou, ha "
            "culturas repetidas sem decisao — e a promessa 'N culturas' esta "
            "a contar entradas."
            % (entradas, len(nomes), len(DUPLICADOS_CONHECIDOS)),
        )

    @staticmethod
    def _config_como_lista():
        """(grupo, subgroup, id, nome_normalizado) de cada entrada."""
        d = json.loads(CONFIG.read_text(encoding="utf-8"))
        out = []
        for g in d.get("groups", []):
            for sg in g.get("subgroups", []):
                for c in sg.get("cultures", []):
                    nome = (c.get("django_nome") or c.get("title") or "").strip().lower()
                    if nome:
                        out.append((g.get("id"), sg.get("id"), c.get("id"), nome))
        return out

    # ------------------------------------------------------------------
    # 5) O `subgroup` de cada cultura e' campo MORTO
    # ------------------------------------------------------------------
    def test_o_subgroup_da_cultura_ou_o_da_pessoa_ou_esta_morto(self):
        """MEDIDO 2026-10-05: cada cultura tem `subgroup` E vive dentro de
        um subgroup com o mesmo id. Os dois concordam no ficheiro.

        **Nao concordam em mutacao.** Provocado: muda-se o `subgroup` de
        "Açaí" para "nativas" e nada acontece — os testes nao caem. So
        mexendo no `subgroup` do PAI e que a hierarquia muda.

        Ou seja: o `subgroup` de cada cultura nao e' lido por nada. E' um
        campo que se mantem certo por coisidencia, nao por regra. Se algum
        dia alguem corrigir a hierarquia por ali, o sistema vai dizer uma
        coisa na pagina e o JSON vai dizer outra, e nao ha nada que as ligue.

        Nao apago o campo — pode haver leitores que nao conheco, e apagar
        dados sem medicao e' o que este projecto ja.Rectificou duas vezes.
        O que este teste faz e' **impedir que alguem confie nele**: se o
        campo e' alterado e nada repara, isso diz-se.
        """
        cfg = self._config_como_lista()
        pais = {}
        for _g, sg, _cid, _nome in cfg:
            pais.setdefault(_cid, sg)

        desencontrados = []
        d = json.loads(CONFIG.read_text(encoding="utf-8"))
        for g in d.get("groups", []):
            for sg in g.get("subgroups", []):
                pai = sg.get("id")
                for cu in sg.get("cultures", []):
                    sub = cu.get("subgroup")
                    if sub is not None and sub != pai:
                        desencontrados.append(
                            "{}: subgroup={!r} mas vive em {!r}".format(cu.get("django_nome") or cu.get("title"), sub, pai)
                        )
        self.assertEqual(
            desencontrados,
            [],
            "%d culturas com `subgroup` diferente do subgroup onde vivem:\n  %s\n"
            "Estao correctas no ficheiro, mas nao tem efeito: mover o grupo "
            "e' mexer no subgroup do pai. Um `subgroup` que parece mand mas "
            "nao manda e' pior do que nao existir — alguem vai corrigir por "
            "ele e a mudanca nao vai acontecer."
            % (len(desencontrados), "\n  ".join(desencontrados[:10])),
        )
