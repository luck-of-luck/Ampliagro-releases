#!/usr/bin/env python3
"""
Build script para gerar packs de cultura (Fase 5).

Lê cultures-config.json + manifest.json e gera:
- app/static/packs/manifest.json (já existe)
- app/static/packs/<subgrupo>.js para cada subgrupo com culturas
- app/static/packs/core.js (núcleo mínimo)
"""

import json
import os
import re
from pathlib import Path


BASE = Path(__file__).parent.parent.parent
STATIC = BASE / "static"
PACKS_DIR = STATIC / "packs"
DATA_DIR = STATIC / "data"
JS_DIR = STATIC / "js"

PACKS_DIR.mkdir(exist_ok=True)


def load_manifest():
    with open(PACKS_DIR / "manifest.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_cultures_config():
    with open(DATA_DIR / "cultures-config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def generate_subgroup_pack(manifest, subgroup_id):
    """Gera o JS para um subgrupo específico."""
    meta = manifest["subgroups"][subgroup_id]
    cultures = manifest["cultures"]

    # Filtra culturas deste subgrupo
    subgroup_cultures = [
        {**c, "id": cid} for cid, c in cultures.items() if c["subgroup"] == subgroup_id
    ]

    pack_code = f"""/**
 * Pack: {meta["title"]} ({meta["id"]})
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: {manifest.get("version", "unknown")}
 * Subgrupo: {subgroup_id} ({meta["culture_count"]} culturas)
 * Grupo: {meta["group_id"]}
 */

(function (global) {{
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = {json.dumps(subgroup_cultures, ensure_ascii=False, separators=(",", ":"))};

  // Metadados do pack
  var PACK_META = {{
    id: '{meta["id"]}',
    title: '{meta["title"]}',
    icon: '{meta["icon"]}',
    group: '{meta["group_id"]}',
    culture_count: {meta["culture_count"]},
  }};

  // Regista as culturas no registry global
  function registerCultures() {{
    if (!global.AmpliagroRegistry) return;
    CULTURES.forEach(function (c) {{
      if (!global.AmpliagroRegistry.cultures) {{
        global.AmpliagroRegistry.cultures = {{}};
      }}
      global.AmpliagroRegistry.cultures[c.id] = c;
    }});
  }}

  // Auto-regista quando carregado
  if (typeof window !== 'undefined' && window.AmpliagroRegistry) {{
    registerCultures();
  }} else if (typeof window !== 'undefined') {{
    // Aguarda registry estar pronto
    var checkRegistry = setInterval(function () {{
      if (window.AmpliagroRegistry) {{
        clearInterval(checkRegistry);
        registerCultures();
      }}
    }}, 100);
  }}

  // Exporta para PackLoader
  if (typeof module !== 'undefined' && module.exports) {{
    module.exports = {{ PACK_META: PACK_META, CULTURES: CULTURES }};
  }}

  // Sinaliza pack carregado
  if (typeof window !== 'undefined') {{
    window.dispatchEvent(new CustomEvent('packloaded', {{ detail: {{ pack: '{meta["id"]}' }} }}));
  }}

}})(typeof window !== 'undefined' ? window : this);"""

    return pack_code


def generate_core(manifest):
    """Gera o core mínimo - registry, widget system, pack loader."""
    return """/**
 * Core Ampliagro - núcleo mínimo (~50 KB gzipped)
 * Registry de culturas, widget system, pack loader
 * Carrega ANTES de qualquer pack
 */

(function (global) {
  'use strict';

  // Registry global de culturas (preenchido pelos packs)
  var AmpliagroRegistry = {
    cultures: {},      // id -> culture object
    widgets: {},       // widgetId -> widget module
    groups: {},        // groupId -> group meta
    subgroups: {},     // subgroupId -> subgroup meta
    packs: {},         // packId -> { installed, version, ... }
  };

  global.AmpliagroRegistry = AmpliagroRegistry;

  // Helper: obtém cultura por ID (fallback para metadata do manifest)
  function getCulture(id) {
    return AmpliagroRegistry.cultures[id] || null;
  }

  // Helper: lista culturas por subgrupo
  function getCulturesBySubgroup(subgroupId) {
    return Object.values(AmpliagroRegistry.cultures)
      .filter(function (c) { return c.subgroup === subgroupId; });
  }

  // Helper: lista culturas por grupo
  function getCulturesByGroup(groupId) {
    return Object.values(AmpliagroRegistry.cultures)
      .filter(function (c) { return c.group === groupId; });
  }

  // Helper: obtém metadados de subgrupo
  function getSubgroupMeta(subgroupId) {
    return AmpliagroRegistry.subgroups[subgroupId] || null;
  }

  // Expõe API
  global.Ampliagro = {
    registry: AmpliagroRegistry,
    getCulture: getCulture,
    getCulturesBySubgroup: getCulturesBySubgroup,
    getCulturesByGroup: getCulturesByGroup,
    getSubgroupMeta: getSubgroupMeta,
  };

  // Sinaliza core pronto
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('coreloaded'));
  }

})(typeof window !== 'undefined' ? window : this);"""


def main():
    manifest = load_manifest()

    print("Gerando packs...")

    # Core
    core_code = generate_core(manifest)
    (PACKS_DIR / "core.js").write_text(core_code, encoding="utf-8")
    print(f"  core.js: {len(core_code)} chars")

    # Packs por subgrupo
    for sg_id, meta in manifest["subgroups"].items():
        if meta["culture_count"] > 0:
            pack_code = generate_subgroup_pack(manifest, sg_id)
            out_path = PACKS_DIR / f"{sg_id}.js"
            out_path.write_text(pack_code, encoding="utf-8")
            print(
                f"  {sg_id}.js: {len(pack_code)} chars ({meta['culture_count']} culturas)"
            )

    print(
        f"\\nTotal packs gerados: {len([s for s in manifest['subgroups'].values() if s['culture_count'] > 0])}"
    )
    print("Concluído.")


if __name__ == "__main__":
    main()
