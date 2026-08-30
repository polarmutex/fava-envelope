from __future__ import annotations

import argparse
import ast
import logging
import re

from beancount import loader
from beancount.core.data import Custom

from fava_envelope.modules.beancount_envelope import (
    BeancountEnvelope,
    EnvelopeSettings,
)


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)-8s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="beancount_envelope")
    parser.add_argument("filename", help="path to beancount journal file")
    args = parser.parse_args()

    # Read beancount input file
    entries, errors, options_map = loader.load_file(args.filename)

    if errors:
        print(errors)

    # Extract EnvelopeSettings from the fava-extension config directive
    settings = None
    for entry in entries:
        if (
            isinstance(entry, Custom)
            and entry.type == "fava-extension"
            and entry.values[0].value == "fava_envelope"
        ):
            cfg_str = entry.values[1].value
            cfg = ast.literal_eval(cfg_str)
            budgets = cfg.get("budgets", [])
            if budgets:
                b = budgets[0]
                settings = EnvelopeSettings(
                    start_date=b.get("start date"),
                    budget_accounts=[
                        re.compile(p) for p in b.get("budget accounts", [])
                    ],
                    mappings=[
                        (re.compile(f), t) for f, t in b.get("mappings", [])
                    ],
                    income_accounts=[
                        re.compile(p) for p in b.get("income accounts", [])
                    ],
                    months_ahead=int(b.get("months ahead", 0)),
                    currency=b.get("currency") or None,
                    negative_rollover=bool(b.get("negative rollover", False)),
                )
            break

    if settings is None:
        logging.error(
            "No fava-extension fava_envelope config found in %s", args.filename
        )
        return

    ext = BeancountEnvelope(entries, options_map, settings=settings)
    df1, df2, df3 = ext.envelope_tables()
    print(df1)
    print(df2)
    print(df3)


if __name__ == "__main__":
    main()
