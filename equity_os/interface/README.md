# `equity_os/interface`

How people and schedules drive the system: the `eqos` and `eqos-operator` entry points with their
composition config, one module per command group, and multi-step workflows. It wires the other
buckets together. Most logic of its own sits in `workflows` (the older end-to-end pipeline, the goal
runner and comparatives); some command modules also hold some, such as
`commands/sourcing/documents_cli.py` (the document-intake pass and issuer selection). Its config classes load the files passed
to them, such as `config/sourcing/fundamentals.yaml` and `config/coverage/watchlist.yaml`.
