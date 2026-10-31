"""Pipeline de scraping con arquitectura Medallion (Bronze → Silver → Gold)."""

from riopaila_qa.scraping.pipeline import STAGES, run_pipeline

__all__ = ["STAGES", "run_pipeline"]
