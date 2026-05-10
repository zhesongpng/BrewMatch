# 0015 DECISION — Acknowledged (Deferred) Red Team Findings

Date: 2026-05-10

## Context

Three findings formally acknowledged as deferred with documented rationale:

- M2-C08: User features always zero during training
- M2-H03: Data leakage via non-random train/test split
- M2-H04: Bean extractor prompt injection

## Decision

All three stem from synthetic data limitations, not code defects. C08 and H03 require real user data to resolve (synthetic CSV has no user columns). H04 is low-risk because users input their own bean labels — not a third-party input surface.

## Why

Fixing C08/H03 without real user data would produce fake user features that mask the real problem. H04's "attacker" is the user themselves, making prompt injection a feature (they can describe their beans however they want) rather than a vulnerability.

## How to apply

Revisit all three when real user data becomes available. H04 should be re-evaluated if the extractor is ever exposed to third-party input (e.g., a shared bean database).
