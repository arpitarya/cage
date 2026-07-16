"""Cage — a *flux*: a deterministic attribution ledger for LLM token traffic.

Meters every call at the provider boundary, collects a savings receipt from each
tool in the stack, and derives the ledger / attribution / counterfactuals — $0,
stdlib-only, independent of any single AI tool. See docs/cage-plan.md.

Public library API (the protocol-targeted adapter, plan §5):

    from cage import meter, record_call, record_receipt

    with meter("code-edit", task="fix-bug") as m:
        resp = client.create(...)
        m.usage(provider="anthropic", model="claude-opus-4-8",
                tokens_in=8600, tokens_out=1500, cached_in=3200)
"""
from cage.metering import (Recorder, meter, record_call, record_human,
                           record_receipt)

__version__ = "0.30.0"
__all__ = ["meter", "record_call", "record_receipt", "record_human", "Recorder",
           "__version__"]
