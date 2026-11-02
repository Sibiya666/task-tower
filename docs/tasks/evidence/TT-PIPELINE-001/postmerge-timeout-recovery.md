# Postmerge workflow timeout recovery

PR #41 merged as `d5cf8953b70caf5329d5173b7fb4a15eaa4df978` after independent PR acceptance and six successful exact-head checks. The Issue remains open until a successful exact-main postmerge cycle and genuine automatic publication.

Actual postmerge run `41451105738`, attempt 1, tested the merged revision. Linux job `125296236871` and macOS job `125296237195` succeeded. Windows job `125296237186` started at `2026-11-02T13:13:27Z` and was cancelled at `2026-11-02T13:28:43Z`. Its test step ran from `13:13:39Z` to `13:28:37Z` and did not report success. The workflow's job timeout was 15 minutes. The exporter retained a failed platform outcome; cancellation is not acceptance.

The independently recorded preceding Windows full-suite run took 1372.835 seconds, longer than this job budget. Final-head push Windows job `125279255267` also succeeded from `12:36:16Z` to `13:06:37Z` (about 30 minutes including setup/cleanup). The independent review confirmed GitHub's explicit annotation: the postmerge job exceeded its 15-minute maximum execution time. Recovery changes only the bounded postmerge job timeout from 15 to 45 minutes. Test commands, exact merge checkout, three-platform matrix, failed-outcome export, source/provenance checks, independent reviewer and publisher-driven closure remain required. No cancelled run is rewritten or counted as passed, no Issue is manually closed, and no execution delivery is reset.

This is the same Issue16 recovery, not permission to merge unrelated work before its main barrier completes. Fresh independent review and green CI must precede the recovery merge. The new exact-main postmerge workflow, independent review and automatic Issue/Project publication remain pending when this note is written.
