# `equity_os/interface`

How people and schedules drive the system: the `eqos` and `eqos-operator` entry points with their
composition config, one module per command group, and multi-step workflows. It wires the other
buckets together; apart from composition, only `workflows` holds logic of its own (the older
end-to-end pipeline, the goal runner and comparatives). Its config classes load the files passed
to them, such as `config/sourcing/fundamentals.yaml` and `config/coverage/watchlist.yaml`.
