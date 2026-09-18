# Jev pilot findings

Jev can grade saved prose outputs quickly, but this pilot did not establish enough practical value to add it to mana's default workflow. Keep the runner optional and advisory. Try it on a real prose-skill change before investing further.

The September 17, 2026 pilot used `jev-1.13.0` with pass at probability <= 0.2, fail at >= 0.8, and uncertain between them. Every question asks whether a violation exists.

| Experiment | Observed result |
|---|---|
| 12 synthetic seed outputs, two questions each | 21 agreements with agent-proposed labels, 3 uncertain judgments, no false passes or false failures. Total request time: 4.254 seconds. |
| 16 fresh model outputs on eight new synthetic source scenarios | 22 agreements with provisional labels, 3 false passes, 6 uncertain judgments, 1 unlabeled judgment. Total request time: 5.762 seconds. |
| Two repeats of the same 16 outputs | No verdict changed across the three evaluations. The largest probability range was 0.09. The same mistakes persisted. |
| 14 new synthetic outputs with an added scope question | The added question caught all six broadened claims and passed seven of eight correct controls, with one uncertain. The existing meaning-loss question caught all six errors and passed all eight controls, so the new question added no coverage on this set. |

The user confirmed the error behind the three false passes: the source guarantees that valid CSV rows are imported, while two rewrites say the importer processes the rest of the file after skipping rows without account IDs. That broadens the guarantee because the source does not establish that missing IDs are the only invalid condition. The false passes are correlated judgments on one source scenario, not independent failures.

Fresh outputs came from Claude CLI with the prose skill supplied as instructions and tools disabled. They test instruction following, not automatic skill discovery. Most labels were agent-proposed; the user confirmed the CSV broadening and approved the later scope-set labels before grading. These small, targeted datasets cannot establish general accuracy, calibration, or review time saved.

The pilot supports a narrow conclusion: Jev caught obvious inventions and dropped conditions, but it consistently missed a confirmed subtle error. Repeated grading did not repair that blind spot. No shipped skill calls Jev, and existing deterministic graders remain in place.

The committed seed examples allow further experimentation. The collection and repeat-run tools were removed from the proposed change after the investigation. Generated outputs and reports remain ignored under `evals/results/`; they are not required to run the retained tool. The optional runner preserves the same probability and error-reporting behavior used in the pilot.
