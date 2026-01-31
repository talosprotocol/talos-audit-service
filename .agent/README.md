# Agent workspace: services/audit

This folder contains agent-facing context, tasks, workflows, and planning artifacts for this submodule.

## Current State
Audit service produces verifiable event streams and integrity signals. SSE endpoints and meta-first semantics are expected where used.

## Expected State
Strong integrity guarantees with clear failure modes and robust backfill and cursor handling where applicable.

## Behavior
Stores and serves audit events, proofs, and integrity state. Exposes event streaming and query APIs for dashboards and services.

## How to work here
- Run/tests:
- Local dev:
- CI notes:

## Interfaces and dependencies
- Owned APIs/contracts:
- Depends on:
- Data stores/events (if any):

## Global context
See `.agent/context.md` for monorepo-wide invariants and architecture.
