# Independent specialist evaluation

Inspected the complete ten-file synthetic project inventory with read-only file reads. Applied the performance and delivery lenses separately using the common evidence contract and schema. No expected assertions or audit implementation scripts were inspected. No fixture commands, tests, builds, benchmarks or deployments were executed.

Performance produced two candidates: the export path proves per-order reads contrary to its batching contract, classified as a static source hypothesis; catalog materialization has explicitly supplied synthetic pre-existing executed evidence attributable to catalog_page. The latter supports measured-bottleneck only within that synthetic workload. This session did not measure performance or independently reproduce the profile.

Delivery produced a strength-100 static release-order candidate after independently inspecting the supplied migration SQL and old-image reader. The release script drops legacy_name before rollout, while the contract requires old-image drain first and the old reader selects that column. This establishes the supplied source contract violation, without establishing a production outage. External orchestration remains unavailable.

Negative cases were inspected and suppressed: the intentionally bounded five-order preview, absence of CI configuration without a violated gate, and the externally owned partner-production pipeline whose implementation cannot be inspected. Both lenses report partial coverage with explicit unavailable scope.

Every candidate quote and line was checked against the fixture source, including the measurement result. Artifact source paths are relative to the fixture root for copied-fixture replay. Remediation and acceptance checks are proposed only. No project files were changed.
