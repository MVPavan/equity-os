# Learnings

Durable, verified, likely-to-recur patterns for **this** repo. Capture only
after a verified fix or a repeated pattern — not speculation. Keep each entry
short: what was observed, why it matters, how to apply it.

Format per entry:

```
## <short title>  (<YYYY-MM-DD>)
- Observed: <what happened / the pattern>
- Why it matters: <consequence>
- Apply: <concrete guidance>
```

## Stale `sync.remote` in `.beads/config.yaml` breaks `bd init`  (2026-08-12)

- Observed: at adoption the working-tree `.beads/config.yaml` carried another
  repo's `sync.remote` (`agent-os.git`, nonexistent); `bd init` tried to clone
  it and failed with "Repository not found". Corrected the remote, init
  succeeded. (Why the earlier init commit f881e51 was reverted is not
  recorded — its committed config already had the correct remote.)
- Why it matters: `bd init` fails closed on a wrong/unreachable `sync.remote`.
- Apply: when adopting into a new repo, set `sync.remote` to the repo's own
  git remote **before** running `bd init`.
