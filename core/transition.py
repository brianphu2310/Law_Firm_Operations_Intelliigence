"""The transition period: one fictional cut-over from LEAP to triConvey (Smokeball) and from InfoTrack to TriSearch.

Every date here is SIMULATED but follows the shape of Smokeball's documented hard cut-over (final data collection at the end of a
working day, a buffer day, go-live the next day; see docs/TRANSITION.md for what is sourced and what is assumed).

    Fri 29 Aug 2025   final data collection: LEAP is frozen, staff stop entering data
    Sat 30 Aug-Mon 1  anything banked or ordered now is in NEITHER system until someone re-keys it
    Tue  2 Sep 2025   go-live in triConvey; TriSearch becomes the search supplier
    Fri 19 Sep 2025   August trust reconciliation due (r48: 15 working days after month end)
    Wed 17 Sep 2025   "today" for the sample data (core.ref.AS_OF)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FINAL_COLLECTION = pd.Timestamp("2025-08-29")       # LEAP frozen at the end of this working day
BUFFER_DAY = pd.Timestamp("2025-09-01")
GO_LIVE = pd.Timestamp("2025-09-02")
RECON_MONTH_END = pd.Timestamp("2025-08-31")         # the trust reconciliation that straddles both systems
RECON_WORKING_DAYS = 15                              # Legal Profession Uniform General Rules 2015, r48(3)
RECON_WINDOW_START = pd.Timestamp("2025-08-01")      # supplier-vs-ledger reconciliation covers the cut-over month and the month after

NSW_LRS_SEARCH_EX_GST = 16.36                        # NSW LRS title / plan / dealing search, 1 Jul 2025 (A$18.00 incl. GST)
TRISEARCH_FEE_RATIO = 34 / 38                        # ASSUMPTION: the app's own platform model prices a TriSearch search at $34 vs $38

# Settings and mistakes planted in the simulation, each tied to a scenario in docs/TRANSITION.md
AUTO_DISBURSEMENT_OFF = (pd.Timestamp("2025-09-08"), pd.Timestamp("2025-09-09"))   # "Automatically create a disbursement" left off
INFOTRACK_STRAGGLER_EVERY = 12                       # one in twelve early-September orders still goes to InfoTrack out of habit
TRUST_SHORT_CLIENT = "Global Trust Bank"
TRUST_OPENING_SHORT_BY = 5799.21                     # a receipt posted in LEAP after the Friday extract ran


def recon_due(month_end: pd.Timestamp = RECON_MONTH_END, working_days: int = RECON_WORKING_DAYS) -> pd.Timestamp:
    """Due date of the monthly trust reconciliation: `working_days` working days after month end (weekends only: public holidays
    are not modelled, and none fall between 1 and 19 September in NSW)."""
    start = np.busday_offset(month_end.date(), 0, roll="backward")          # last working day on or before month end
    return pd.Timestamp(np.busday_offset(start, working_days))


def working_days_elapsed(as_at: pd.Timestamp, month_end: pd.Timestamp = RECON_MONTH_END) -> int:
    """Working days between month end and `as_at` (the number the bookkeeper watches while the r48 clock runs)."""
    start = np.busday_offset(month_end.date(), 0, roll="backward")
    return int(np.busday_count(start, as_at.date()))


def normalise_ref(ref: str | None) -> str:
    """Matter reference as a supplier invoice might carry it ('m2024-0153', 'M 2024 0153') reduced to letters and digits."""
    return "".join(ch for ch in (ref or "").upper() if ch.isalnum())
