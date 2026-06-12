# Phase 3H Controlled Explanation Integration Plan

## Goal

Phase 3H.2 connects the isolated guarded explanation layer to the existing audit
output without changing Phase 2 decisions. Phase 3H.3 adds deterministic
end-to-end and demo coverage without loading a real model.

The official MVP explanation remains the deterministic template.

## Existing Audit Result

`AgentInvoiceProcessor.process_extracted_invoice()` is the existing real audit
path. It runs the fixed tools, `ThreeWayMatcher`, `PolicyRAG`, and `RiskEngine`,
then creates an `AuditReport`.

The following values are already decided before the explanation layer runs:

- validation booleans and mismatches;
- policy flags and reason codes;
- risk level;
- recommended action;
- evidence;
- legacy anomaly explanation.

The explanation layer must treat all of them as read-only.

## Integration Point

The safest integration point is immediately after `_build_report()` returns and
before the report JSON is persisted and returned.

At that point:

- Phase 2 matching and risk calculation are complete;
- no explanation output can influence tool selection or review submission;
- the final report can receive additive explanation metadata;
- the existing generic audit trace repository is available.

A small Phase 3 explanation adapter will convert the completed invoice,
validation result, risk assessment, policy flags, and evidence into
`CanonicalAuditFacts`. It will map only existing reason codes and mismatch
fields to the fixed Phase 3 anomaly enum. It will not infer new risk, action, or
anomaly facts.

## Execution Modes

### Template

`template` is the default and official mode.

- no rewrite provider is required;
- no model is loaded;
- no network or GPU is used;
- the deterministic renderer produces the final explanation;
- identical facts produce identical text and facts hash.

### Shadow

`shadow` must be selected explicitly and requires an injected provider.

- the provider output is checked by the guard;
- raw output, guard result, and fallback reason are recorded;
- the official explanation remains the deterministic template even when the
  guard passes;
- no production model provider is configured by default.

### Experimental

`experimental` must be selected explicitly and requires an injected provider.

- a rewrite is used only after the guard passes;
- guard failure, unavailable provider, empty output, invalid output, parsing
  failure, or provider runtime failure returns the deterministic template;
- high-risk cases always use the deterministic template;
- failures do not propagate to the API caller.

Tests will use fake providers only. This phase will not load Qwen or a LoRA
adapter.

## Audit Trail Choice

This integration selects **Option A**, reusing the existing generic
`audit_traces` table and `AuditTraceRepository.create_trace()`.

One `explanation_render` step will record:

- canonical facts hash;
- template, prompt, model, and adapter versions;
- mode and whether a rewrite was used;
- raw rewrite output when available;
- guard result;
- fallback reason;
- final explanation.

The existing table already stores arbitrary JSON input and output payloads, so
no table, schema change, or migration is required.

## API Compatibility

`AuditReport` will receive one optional additive `explanation` object. Existing
fields, including `anomaly_explanation`, keep their current meaning.

The metadata may contain:

- `explanation_text`;
- `explanation_source`;
- `facts_hash`;
- `template_version`;
- `prompt_version`;
- `used_rewrite`;
- `fallback_reason`;
- `guard_passed`.

Old clients can ignore the new field. Existing stored JSON remains valid
because the field is optional. The upload response may expose the same
explanation object additively while preserving all old keys.

No database column is added because `audit_report_json` already stores the
report as JSON.

## Phase 2 Invariants

The integration must not modify:

- three-way matching results;
- duplicate detection;
- risk level;
- recommended action;
- tool calls;
- review submission;
- policy flags;
- evidence or mismatches.

The explanation service receives snapshots after these values are finalized
and has no write-back path to Phase 2 objects.

## Canonical Fact Mapping

The adapter will preserve:

- `anomaly_types`: mapped only from existing reason codes and mismatch fields;
- `evidence`: copied from the completed report;
- `missing_fields`: derived only from absent extracted PO/GRN values already
  visible in the completed audit input;
- `risk_level`: copied from `RiskAssessment`;
- `recommended_action`: copied from `RiskAssessment`.

A clean invoice may have an empty anomaly list. The deterministic template will
represent that as no anomaly rather than inventing one.

## Test Plan

Automated tests will cover:

- template default behavior and stable output/hash;
- additive API response compatibility;
- unchanged Phase 2 validation, risk, action, anomaly, evidence, and missing
  facts;
- shadow trace-only behavior with fake providers;
- experimental guard pass and every fail-closed fallback;
- high-risk forced template behavior;
- fixed offline demo cases with no network, GPU, Qwen, or ModelScope.

## Guard Limitations

The current guard is a conservative structured-rule guard, not a production
semantic verifier.

It checks declared patterns for identifiers, amounts, vendors, selected policy
and approver terms, anomaly labels, fixed sections, risk, and action. It does
not prove general semantic equivalence and may not detect paraphrased,
implicit, or unmodeled claims.

For that reason:

- deterministic template remains the default;
- LoRA remains shadow or experimental only;
- real LoRA inference is not enabled;
- API default behavior has no model dependency;
- LoRA cannot be described as a production default explainer.
