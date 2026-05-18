#!/usr/bin/env python3
"""Smoke experiment for `bitcoin-regime-lab`.

No network, no credentials, no public claim. It only proves that the generated
lab has an executable domain-native tool with baseline/null language.
"""

import argparse
import json
from datetime import datetime, timezone

BOUNDARY = {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = {
        "schema": "bitcoin-regime-lab.request_smoke.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain_kind": "bitcoin-regime",
        "verdict": "REFERENCE_BOUNDARY_ONLY",
        "baseline": "naive/request-preserving baseline required before interpretation",
        "null": ['shuffle_or_permutation_null', 'domain_native_control_null'],
        "boundary": BOUNDARY,
        "public_claim": False,
        "trading_signal": False,
        "operational": False,
        "next": "replace smoke with domain-native experiment after first reviewed cycle",
    }
    print(json.dumps(payload, indent=2 if args.json else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
