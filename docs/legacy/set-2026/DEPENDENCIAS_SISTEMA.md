# Dependências de sistema do AmplIA

O AmplIA roda Python puro na maior parte, mas duas dependências **não são
pip** e precisam estar no sistema operacional. Nenhuma delas é código: são
binários do SO.

---

## 1. Tesseract — OCR de documento impresso

### Para quê

Ler **NFe impressa em PDF ou foto** — nota de fornecedor, a segunda maior via de
entrada de insumo. O pipeline tem três motores, nesta ordem:

| documento | motor | o que acontece |
|---|---|---|
| NFe **em XML** | `nfe-xml` | determinístico, confiança 1.0, nem passa por OCR |
| NFe **impressa** (PDF/foto) | `tesseract` | OCR determinístico, offline |
| **Caderno manuscrito** | — | OCR não serve; visão assistida (não implementado) |

**XML não precisa de Tesseract.** É o caminho recomendado: mais confiável,
mais rápido, e é o formato que o portal da NF-e entrega por padrão.

### Como saber se está faltando

`GET /api/amplia/` não expõe isso, mas o diagnóstico é público:

```python
from app.ia.ingestao import ocr
print(ocr.diagnostico())
```

```python
{'pillow': True, 'tesseract': False,
 'tesseract_cmd': 'tesseract', 'modo_padrao': 'nfe-xml',
 'nota': 'Sem OCR instalado: imagem impressa nao vira texto automaticamente...'}
```

Na UI, o produtor **não vê erro**. Vê um rascunho com a frase:

> "Este servidor não tem OCR instalado, então a foto não foi lida. Copie os
> números ou envie a NFe em XML — o XML já vem estruturado e não precisa de
> OCR. Modo rascunho."

Essa degradação explícita é intencional e é o que `app/ia/ingestao/ocr.py`
corrige: o comportamento anterior era devolver `"imagem JPEG 800x600"` com zero
aviso, e o produtor acreditava que a nota estava em branco.

### Instalação

**Windows**

```powershell
winget install UB-Mannheim.TesseractOCR
# ou baixe de https://github.com/UB-Mannheim/tesseract/wiki
# e adicione a pasta ao PATH
```

Depois, aponte o caminho se não estiver no `PATH`:

```python
# config/settings/base.py
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

**Linux**

```bash
sudo apt install tesseract-ocr tesseract-ocr-por
```

**macOS**

```bash
brew install tesseract tesseract-lang
```

### Detalhes que costumam dar trabalho

**Português.** `ocr.py` pede `lang="por+eng"`. Sem o pacote de idioma
português, o Tesseract **não falha** — ele transcreve errado em inglês, o que
é o pior modo de falhar:

```bash
sudo apt install tesseract-ocr-por   # Debian/Ubuntu
brew install tesseract-lang          # macOS
```

**Não confunda `import pytesseract` com Tesseract instalado.** O pacote Python
só chama um executável externo. Numa imagem de container o import passa e o
binário não existe — é por isso que `tesseract_disponivel()` verifica os dois
e consulta `get_tesseract_version()`.

**Falta de memória é o modo comum de falha.** Uma foto de celular tem 3–12 MB.
O limite de 12 MB e a validação de 240×80 px estão em `ocr.py` por isso.

**O binário NÃO é compartilhado com o app.** Nada no `Ampliagro` chama
`subprocess` direto; o acesso é só por `pytesseract`, e o binário fica em
`PATH` (ou no `tesseract_cmd`).

---

## 2. Redis — fila (opcional)

### Para quê

Celery, que hoje é usado para **áudio longo** em fila. Não é necessário para o
caminho normal.

### Estado atual

O broker está configurado (`config/settings/base.py`), mas **não há worker nem
Redis nesta máquina**. Por isso o fallback de áudio é **síncrono no request**:
um áudio de 30 s cabe no tempo de um request, e depender só de Celery faria a
funcionalidade entrar no ar e nunca funcionar.

```bash
redis-server                      #ou
docker run -p 6379:6379 redis
```

Worker:

```bash
celery -A config worker -l info
```

### O que NÃO depende de Redis

- Transcrição no cliente (Whisper no navegador) — sem backend, sem fila;
- OCR de NFe;
- Queda do LLM para `sandboxBridge`;
- Toda a execução governada.

Se Redis não subir, **o produto funciona**. Ele só faz a fila de áudio longo
deixar de ser síncrona.

---

## 3. WebGPU — o navegador, não o servidor

O que realmente limita o produto é o **aparelho do produtor**, não o servidor.

| Precisa | De quê | Sem isso |
|---|---|---|
| SmolLM2-1.7B (o raciocínio) | WebGPU | cai para `Qwen2-0.5B`; sem ambos, modo servidor |
| Whisper-tiny (a transcrição) | WebGPU | cai para WASM/CPU — funciona, ~5–10× mais lento |

O LLM e o Whisper **não rodam ao mesmo tempo**: `criarSerializadorGpu()` em
`whisper-audio.js` garante exclusão mútua do dispositivo, porque eles
disputam a mesma GPU.

Chrome/Edge 113+ no Android e no desktop têm WebGPU. Safari 18+ no iOS também
tem, com menos maturidade — vale medir antes de prometer 2–4 s lá.
