"""MYOB -> n8n -> Snowflake integration layer for the D'Agostino Legal dashboard.

All data is SIMULATED: integration/myob_export.py re-shapes the app's own fixed-seed model (core.model) into the JSON that the
MYOB Business (AccountRight) API v2 returns, so the pipeline's marts can be reconciled to the numbers the dashboard shows.
"""
