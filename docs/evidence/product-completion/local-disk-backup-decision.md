# Local-disk backup decision

**Recorded:** 2026-10-02. **Authority:** current explicit user instruction.

The user requires disk-only backup, prohibits cloud use, and accepts possible loss of retained documents. This supersedes the Gold goal's off-machine/durable-destination requirement for this execution scope; other V11 obligations remain unchanged. A second copy on the same local disk is accepted by the user and is not represented as off-machine durability.

The coordinator created a gitignored local archive and independently extracted it. All 277 inventoried files were checked against their recorded sizes and SHA-256 values. Exact archive and restore paths, hashes, counts and outcomes are in `local-disk-backup-restore.json`. Raw sources and backups remain uncommitted. No cloud service was used.
