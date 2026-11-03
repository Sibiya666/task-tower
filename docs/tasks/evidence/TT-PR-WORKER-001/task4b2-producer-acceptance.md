# Task4b2 producer prerequisites: bounded acceptance

The private host context now binds an existing genuine PR journal by physical identity, exact schema and validated rows inside an explicit read-only transaction. Missing remains null; appearance or replacement requires a new context. Normal journal writes do not invalidate the context through a mutable database hash.

Opt-in `prepare_review(..., private_context=context)` binds actual private provenance and a canonical host UUID location inside the immutable input. Existing calls retain their v1 fields. Streaming canonical UTF-8 identity and a fixed512MiB prelaunch record reserve reject oversize data without truncation. These helpers do not accept imported process proof.

Independent development reviewer70b32225-0f4b-4d5f-89a6-e2925d4edf19 APPROVED this bounded code against the frozen source in task4b2-producer-source.json. Review process83.906s, exit0, cleanup confirmed, complete292608 stdout/7974 stderr, source/executable unchanged. Verdict: task4b2-producer-native-review.json. Affected contract was separately approved by reviewer97e46afd; see task4b2-contract-review.json.

Root verification:

- Context/current regressions:36 tests,102.295s, OK; actual102.625s, exit0, complete output, cleanup and unchanged source. Completion evidence runtime/verification/pr17-own-journal-green, stderr SHA e2f8601d5db259df9fbd80cf6f125f26213213c5058fc17709be3faee9e593f2.
- Final genuine preparation, own-journal and budget regressions:15 tests,77.799s, OK; actual78.125s, exit0, complete output, cleanup and unchanged source. Evidence runtime/verification/pr17-preparation-provenance-green-fix1, stderr SHA3d5d92fad97cb1f37653b027ce8881e51541f7b0de8068298acd5bff7d6617c5.
- Actual stage/current authority, hardened Git preparation, existing default format, private revocation, outside/dictionary locators, existing corrupt rows, schema/replacement/appearance, exact UTF-8 byte boundary and oversize refusal are exercised. The stage fixture runs real contained processes; these fresh tests are not original legacy acceptance.

Historical RED results and the initial missing-import failure remain in local verification evidence. Two initial SQLite fixture cleanup errors were corrected by explicitly closing connections and rerunning their meaningful failure cases before implementation. No complete-suite pass is claimed for this candidate.

Strict prepared/review record readers, Task5 persistence/lifecycle, effects4c, CLI5, mandatory Task3L, actual all-writer authorization, server protections, whole-PR review/CI and exact-main acceptance/automatic closure remain required. This is not whole Task4b2 or Issue17 completion.
