# Conservative research position

## Implemented contribution

An inspectable experimental integer VM combines isolated immutable snapshots,
value-only AST mutation, immutable external objectives, mandatory static and
finite-case behavioral gates, hierarchical root accounting, pinned active
execution, journal-before-commit, and full seeded semantic replay. Regression
experiments contrast this architecture with the supplied mutable-line prototype.

## Potential research contribution

The thesis to investigate is **transactional invariant-preserving self-modification
under immutable objectives and hierarchical resource budgets**. A future paper
could formalize admission/commit and resource conservation, then evaluate objective
attacks, nested computation, rollback and replay against ablated implementations.
Current finite oracle cases do not prove general invariant preservation.

## Adjacent work and retrieved primary sources

Search date: 2026-10-11. This was a bounded conceptual search, not exhaustive
systematic novelty clearance. No publication novelty is established.

| Area | Primary source | Relationship/difference |
|---|---|---|
| Genetic improvement | Langdon, Genetic improvement of programs (2015), [UCL repository](https://discovery.ucl.ac.uk/id/eprint/10074596/) | Program mutation and objective-based search already exist; our greedy search is not a novel algorithm |
| Proof-carrying code | Necula, Proof-carrying code (1997), [ACM DOI](https://doi.org/10.1145/263699.263712) | Proof certificates establish properties; VeriMorph uses checks and finite testing, not PCC |
| Runtime assurance/self-adaptation | Rivera et al., An Architectural Description of the Simplex Architecture (1996), [CMU SEI](https://www.sei.cmu.edu/library/an-architectural-description-of-the-simplex-architecture/) | Trusted protection around untrusted/adaptive behavior predates this runtime |
| Dynamic hot-swapping/state transfer | Hayden et al., State Transfer for Clear and Efficient Runtime Upgrades, [author paper](https://www.cs.tufts.edu/~jfoster/papers/ekiden.pdf) | Runtime upgrades and state transfer are established; this VM pins frames and avoids mutable state migration |
| Automatic repair/synthesis | Yuan and Banzhaf, ARJA (2017), [author preprint](https://arxiv.org/abs/1712.07804) | Structured mutation, filtering and fitness search are established; constrained safety integration must be evaluated separately |

Capability security, transactional commit and bounded evaluators are established
ideas. Their integration here is an implemented systems contribution; it does not
by itself establish a new theorem or research novelty. The author-paper sources
above support this conservative position, not comparative superiority.

## Unproven novelty and missing research evidence

No exhaustive prior-art review, mechanized semantics/proof, theorem, comparison to
external runtimes, broad workload corpus, held-out generalization study, or independent
replication exists. Benchmarks characterize overhead only. Research artifact
readiness is stronger than paper readiness. Do not market this repository as a
novel verified language or a solved self-modification safety problem.
