# docs/example — copy-from contracts

Worked, copy-from examples of cage's surfaces. Each file is a **contract**: the
shape a user or agent can rely on. When a surface changes, update the matching file
in the same change (docs-in-sync law; row in [../DOC-REGISTRY.md](../DOC-REGISTRY.md)).

Written in short points, not walls of prose (the doc-style rule in CLAUDE.md).

| File | Surface |
|---|---|
| [cli.md](cli.md) | Command-line verbs — read, capture, manage |
| [debug.md](debug.md) | Debug + diagnostics env vars and `cage doctor` |
| [setup.md](setup.md) | Wiring cage into a project / agent |
| [toml-config.md](toml-config.md) | `cage.toml` — budgets, pipeline order, capture |

Authoritative behavior always lives in the code and `cage --help` / `cage query`;
these examples are the friendly front door, kept true to it.
