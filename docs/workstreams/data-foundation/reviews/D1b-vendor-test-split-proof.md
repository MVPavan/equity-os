# Protected vendor producer test split

Status: scoped structural repair verified, 2026-10-13, `eqos-u0u.27`; fresh formal gate pending.

Frozen batch `5151576` passes **3,218 tests / 8 existing skips**, complete Ruff lint/format,
strict mypy on270 sources and privacy rails. Its formal exit is still CONTRACT/nonzero because
the protected producer acceptance module has938 lines, exceeding the gate's800-line limit.
That result is retained; source-code/type/privacy PASS does not waive the structural stop.

Root moves exactly five non-test helper declarations to `vendor_inputs_support.py` beside
the original test module, leaving all seventeen test function declarations and their node IDs
in `test_compare_vendor_inputs.py`. Complete function/class semantic AST inventories match
exactly **22/22**, including decorators/defaults; all assertion ASTs match **72/72**. Helper
uses of `Path(__file__).parent` still refer to the same tests directory. Only imports/format
and module placement change; no fixture body, numeric literal, assertion or production file
changes. The new helper is303 lines and main test module679, each below800.

Before-file SHA-256: `fd58cdb687a1f8c86c2ae063683669e5b35f5136f4a7bc353dc030bcbc1ab46f`.
After test SHA-256: `fcb97ca12df2199bc2cbab8c727b199778167fff262f0ff3fce83ebc6bcf6d29`.
New helper SHA-256: `788de54731167bf59e42764c6bd44375799badd21a844a4136959362b9cb9bd9`.
The before bytes remain in scratchpad. Fresh entire producer matrix is **38 passed in35.34s**;
scoped Ruff lint/format pass. Root explicitly authorizes resealing both acceptance and new helper
using this mechanical evidence; the original two producer behavioral RED outcomes are unchanged.
The helper must be explicitly added to the protected proof, not left outside its file hashes.

No full formal PASS is claimed until the fresh combined gate returns0 after this repair. Public
run integration and positive failed-XBRL witness support remain independently in progress.
