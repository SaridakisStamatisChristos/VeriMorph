# Original prototype and redesign rationale

The supplied experiment combined a lexer/parser/AST, mutable source lines,
recompilation, optimization, evolutionary search, resource counters and audit
logging. All five originals are preserved unchanged under legacy/original-prototype.
Their historical quality labels are retained as historical bytes, not endorsed.
They are excluded from installation and runtime imports.

Run `python scripts/reproduce_legacy.py` and compare
`docs/evidence/legacy-reproduction.json`. The probes operate only on supplied local
code, disable network, and cap recursive instrumentation.

| Observation | Reproduction | VeriMorph consequence |
|---|---|---|
| Live source can become syntactically invalid | MODIFY_LINE writes `RETURN (`; compilation fails afterward | isolated candidate and atomic commit |
| Evolution can mutate fitness | seed 0, attempt 6 changes fitness RETURN 100 -> 101; main unchanged | external immutable objective |
| Child evaluation resets accounting | eight nested score entries each observe parent steps=2 with local max_steps=3 | one root account |
| Demo line 2 is wrong target | line 2 is inside fitness; demo changes it to assignment while main x=5 stays unchanged | AST paths plus parent snapshot |
| Static analyzer is advisory | injected warning logs but compilation succeeds; actual analyzer checks only nesting/functions | mandatory fail-closed static gates |
| HMAC is calculated/logged only | no expected trusted MAC input or comparison | explicit integrity semantics and replay |

Recursive instrumentation stops child creation at the eighth score entry. Fifteen
score attempts appear because unwinding parents also try candidates, which are
stopped by the same probe. This is bounded evidence of counter separation, not
an unbounded exploit or a hard timeout measurement.

The new language intentionally changes scope, failure, mutation and evolution
semantics. The old optimizer and SEND_SOURCE are not carried forward. The original
files remain useful for evidence, never as the trusted runtime. Their byte hashes
are checked by scripts/check_legacy.py and CI.
