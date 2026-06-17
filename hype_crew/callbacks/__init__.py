"""Hype Crew observability — Supabase logging of runs + stages.

Post Bug-1 refactor: no ContextVar, no task_callback. Flow passes run_id
explicitly to init_run / log_stage / finalize_run.
"""
from .supabase_logger import init_run, log_stage, finalize_run

__all__ = ["init_run", "log_stage", "finalize_run"]
