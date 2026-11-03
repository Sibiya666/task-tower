# Issue21 Task3 independent code review

Verdict: REJECT / blocking P1 finding. Reviewed independently; reviewer did not implement this candidate. No native execution, network effects, full-suite run, source edits, commit or push.

Binding: checkout task-tower-opencode HEAD 62427c3e99dc89427a3c721b1321067018b28a11. Verified actual four file hashes against runtime/opencode21-task3-freeze.json:
- task_tower/opencode_adapter.py 042f148c5c88449634fa645eb320fd916416dda9e76fc6a122cff6e178e02e1d
- tests/test_opencode_events.py 6095c04f7f76177b945f992081557442db9ebd5bd4d1f8f2d302333df1b07383
- tests/fixtures/opencode-v2/live-reconciled-stop.synthetic.jsonl 761b5f7e8fe4b97e6fbf32d7fcbb3f00b2a02ec5f7b26b526a1f1a76d8786d91
- tests/fixtures/opencode-v2/SOURCE.md 5bb0120ddcfde04be9f59fcebf3c0ac9ffd6de8878a43d56714cc8a3f2f0d06c

Reviewed whole four-file diff, actual candidate adapter and harness interfaces, approved design/Task3 plan, implementation/brief, pinned noninteractive.ts plus token/finish schemas and provenance manifest. Existing closed dispatch is unchanged. Concurrent test_opencode_transport.py CI fixture repair is excluded. Existing reported 112 focused passing tests were not redundantly rerun.

## P1: enforce retained normalized event metadata limit

The design line 131 requires at most 65536 bytes retained normalized event evidence; plan line 47 repeats this bound. parse_opencode_events initializes seen, steps, finishes, part_owners and tool_calls, then inserts identities/digests for every distinct event without any metadata accounting or overflow check. The fixed-size public digest/result does not bound the retained normalized identity evidence used during parsing. Raw tool-call IDs are also retained as dictionary keys. Event count and stdout limits do not enforce this separate accepted bound.

Independent concrete probe: import actual tests.test_opencode_events.EventTests/event helpers and call actual parser on step_start, 1200 text events with unique prt_unique_<index> identities, then step_finish. A Python trace callback at parser return measures sum(len(canonical([key,value]))) over each retained dictionary. It returns valid=true, terminal_stop=true, event_count=1202. Retained serialized entries: seen=125112, steps=22, finishes=18, part_owners=44578, tool_calls=0, total=169730 bytes. Even seen alone exceeds 65536. This excludes Python object overhead, so is a conservative witness. Probe completed with bundled Python exit0. A first inefficient tracing attempt was interrupted; only the completed return-time trace is evidence.

Required correction: apply explicit deterministic accounting to all retained normalized identity/digest state (or redesign its bounded representation), reject before admitting an entry that exceeds the accepted cap, and add meaningful exact-boundary/overflow tests covering distinct parts, steps and tool calls. Preserve duplicate idempotence and conflict checks; do not replace identity validation with an accepting digest shortcut. A changed candidate needs fresh independent review.

Other reviewed behavior: five fixed argv items, all-file normalized instruction input and exact request/schema binding, exclusive frozen transport binding, source-specific differing start/finish identities and projected suffix ordering, strict session/type/duplicate handling, process/EOF/hash proof, raw output privacy and unchanged generic/pipeline guards are consistent with Task3 scope. Parser does not itself establish bound local-result completion or Task4/native qualification; neither is approved here. No additional blocking finding identified in this review.
