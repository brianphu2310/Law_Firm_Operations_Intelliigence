"""The transition-period helpers: dates and the trust reconciliation clock (core/transition.py)."""
import pandas as pd

from core import transition as T
from core.ref import AS_OF


def test_cutover_follows_the_documented_shape():
    assert T.FINAL_COLLECTION.day_name() == "Friday" and T.BUFFER_DAY.day_name() == "Monday" and T.GO_LIVE.day_name() == "Tuesday"
    assert (T.GO_LIVE - T.FINAL_COLLECTION).days == 4                 # final collection, weekend, buffer day, go-live


def test_august_reconciliation_is_due_on_the_fifteenth_working_day():
    assert T.recon_due() == pd.Timestamp("2025-09-19")                # 1 Sep is working day 1 (31 Aug is a Sunday)
    assert T.recon_due(pd.Timestamp("2025-09-30")) == pd.Timestamp("2025-10-21")


def test_working_days_left_on_the_sample_date():
    assert T.working_days_elapsed(AS_OF) == 13 and (T.RECON_WORKING_DAYS - T.working_days_elapsed(AS_OF)) == 2


def test_reference_normalisation_survives_retyping():
    assert T.normalise_ref("m2025-0413") == T.normalise_ref("M-2025-0413") == "M20250413"
    assert T.normalise_ref(None) == ""
