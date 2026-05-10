# 0014 DECISION — Optuna Study Persistence for Recipe Optimizer

Date: 2026-05-10

## Context

M2-M17: Optuna study created fresh on every optimization call. Historical trials lost between sessions, preventing warm starts.

## Decision

Added `study_path` parameter to `RecipeOptimizer.__init__()`. When set, loads prior study via `joblib.load` and saves after optimization via `joblib.dump`. Default is `None` (no persistence, backwards-compatible).

## Why

Warm starts let the optimizer learn from past optimizations for the same user/bean combo. Defaulting to `None` keeps existing usage unchanged — only opt-in when persistence is desired.

## How to apply

Production deployment should set `study_path` to a per-user file location. Demo mode should leave it `None` to avoid file I/O overhead.
