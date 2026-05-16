"""Movement — verify_assertions (universal).

γ CALCOLO. Esegue test riproducibili degli assiomi/fatti del dominio attivo
e produce PASS/FAIL/SKIP. Il seed_integrator successivo converte FAIL in
tensioni, PASS universale (tutti pass) in tensione META "simmetria sospetta".

Senza questo movement, il seed_integrator non ha materiale a sufficienza per
cristallizzare → seed.json si svuota cycle dopo cycle. Operatore (29/04):
"il ciclo A5 del demo non chiude — manca verify_assertions".

Il movement e' UNIVERSALE: non conosce il dominio. Cerca opzionalmente
domains/<domain>/assertions.py che esporta:

    ASSERTIONS: list[dict] = [
        {
            'id': 'A1',
            'claim': 'qualunque claim testabile in linguaggio naturale',
            'source': 'riferimento alla documentazione del dominio',
            'test': callable_che_ritorna_dict_con_status,
        },
        ...
    ]

Ogni callable di test riceve nessun argomento (o solo uno opzionale per
data dir) e ritorna:

    {
        'status': 'PASS' | 'FAIL' | 'SKIP',
        'detail': 'breve descrizione di cosa ha trovato',
        'metric': <opzionale, valore numerico verificato>,
    }

Domini diversi (physics, finance, biology, ...) shippano i propri assertions.py.
Lab D-ND demo physics: A1-A5 derivati dal modello D-ND.
Lab finance custom: assiomi del dominio finanziario (es. "no arbitrage in
markets efficienti"). Operatore + assistente di installazione decidono.

Critical=False: se assertions.py non esiste o crasha, marca pending e prosegue.
Il seed_integrator gestisce il caso "verify_assertions non disponibile".
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import config as cfg
from core import paths
from core.lab_agent import CycleContext, register_movement

logger = logging.getLogger(__name__)


def verify_assertions(ctx: CycleContext) -> None:
    """Run domain assertions, persist PASS/FAIL/SKIP, surface in metrics.

    Fail-soft: missing assertions module, malformed list, individual test
    crash → marked pending, cycle continues. The seed_integrator must be
    robust to absence of this metric.
    """
    params = cfg.movement_params(ctx.config, "verify_assertions")
    domain = ctx.domain

    # Locate domain assertions module (optional)
    assertions_path = Path("/opt/D-ND_LAB") / "domains" / domain / "assertions.py"
    if not assertions_path.exists():
        ctx.record_skipped("verify_assertions", "no domains/<domain>/assertions.py")
        ctx.metrics.setdefault("verify_assertions", {}).update(
            n_pass=0, n_fail=0, n_skip=0, results=[]
        )
        return

    # Load assertions module (isolated namespace, not added to sys.modules)
    try:
        spec = importlib.util.spec_from_file_location(
            f"_dnd_assertions_{domain}", assertions_path
        )
        if spec is None or spec.loader is None:
            raise ImportError("could not create spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assertions = getattr(module, "ASSERTIONS", None)
        if not isinstance(assertions, list):
            verifica_asserzioni = getattr(module, "verifica_asserzioni", None)
            if not callable(verifica_asserzioni):
                raise ValueError("ASSERTIONS is not a list and verifica_asserzioni() is missing")
            direct_results = verifica_asserzioni()
            if not isinstance(direct_results, list):
                raise ValueError("verifica_asserzioni() did not return a list")
            assertions = [
                {
                    "id": str(item.get("id", "?")),
                    "claim": str(item.get("claim", item.get("detail", ""))),
                    "source": str(item.get("source", "verifica_asserzioni")),
                    "test": (lambda item=item: item),
                }
                for item in direct_results
                if isinstance(item, dict)
            ]
    except Exception as e:
        logger.warning("verify_assertions: cannot load %s: %s", assertions_path, e)
        ctx.movement_status["verify_assertions"] = f"pending: load failed: {e}"
        ctx.metrics.setdefault("verify_assertions", {}).update(
            error=str(e)[:300], results=[]
        )
        return

    # Run each assertion test, collect results
    results: list[dict[str, Any]] = []
    for entry in assertions:
        if not isinstance(entry, dict):
            continue
        aid = entry.get("id", "?")
        claim = entry.get("claim", "")
        source = entry.get("source", "")
        test_fn = entry.get("test")
        if not callable(test_fn):
            results.append({
                "id": aid, "claim": claim, "source": source,
                "status": "SKIP", "detail": "test is not callable",
            })
            continue
        try:
            r = test_fn()
            if not isinstance(r, dict) or "status" not in r:
                results.append({
                    "id": aid, "claim": claim, "source": source,
                    "status": "SKIP",
                    "detail": "test did not return dict with 'status'",
                })
                continue
            results.append({
                "id": aid, "claim": claim, "source": source,
                "status": str(r.get("status", "SKIP")).upper()[:10],
                "detail": str(r.get("detail", ""))[:400],
                "metric": r.get("metric"),
            })
        except Exception as e:
            tb = traceback.format_exc().splitlines()[-3:]
            results.append({
                "id": aid, "claim": claim, "source": source,
                "status": "SKIP",
                "detail": f"test exception: {e} | {' | '.join(tb)}"[:400],
            })

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")

    # Persist record
    out_dir = paths.domain_data_dir(domain) / "assertions"
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "domain": domain,
        "timestamp": ctx.timestamp,
        "assertions_path": str(assertions_path),
        "n_pass": n_pass,
        "n_fail": n_fail,
        "n_skip": n_skip,
        "n_total": len(results),
        "results": results,
        "marked_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / f"assertions_{ctx.timestamp}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False)
    )

    ctx.record_success(
        "verify_assertions",
        n_pass=n_pass, n_fail=n_fail, n_skip=n_skip, n_total=len(results),
    )
    # Make results available to downstream movements (especially seed_integrator)
    ctx.metrics.setdefault("verify_assertions", {}).update(
        n_pass=n_pass, n_fail=n_fail, n_skip=n_skip, n_total=len(results),
        results=results,
    )
    logger.info(
        "verify_assertions: %d PASS, %d FAIL, %d SKIP on %d total",
        n_pass, n_fail, n_skip, len(results),
    )


register_movement("verify_assertions", verify_assertions)
