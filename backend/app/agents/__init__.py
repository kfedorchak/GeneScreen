"""Agents that enrich candidate dependencies.

Each agent returns one of the *Report Pydantic contracts in schemas.py, so a
stub and a future LLM-backed implementation are interchangeable. `targetability`
is LIVE against the Open Targets GraphQL API (with an on-disk cache); the others
are deterministic stubs clearly labeled as simulated.
"""
