import pytest

import seed
from engine import InsufficientPoints, PointsLedger, QuestRecommender, RiskModel, level_for, streak


def test_recommendations_exclude_completed_and_sorted():
    youths, quests, _, _ = seed.build()
    reco = QuestRecommender(youths, quests)
    y = next(iter(youths.values()))
    out = reco.recommend(y.id, k=5)
    assert all(r["quest"]["id"] not in y.history for r in out)
    scores = [r["score"]["total"] for r in out]
    assert scores == sorted(scores, reverse=True)


def test_ledger_idempotent_and_no_double_spend():
    led = PointsLedger()
    assert led.credit("a", 100, "q", "k1")
    assert led.credit("a", 100, "q", "k1") is None      # duplicate check-in ignored
    assert led.balance("a") == 100
    led.debit("a", 60, "r", "d1")
    with pytest.raises(InsufficientPoints):
        led.debit("a", 60, "r", "d2")
    assert led.verify()


def test_ledger_tamper_detected():
    led = PointsLedger()
    led.credit("a", 100, "q", "k1")
    led.credit("a", 50, "q", "k2")
    led._entries[0]["amount"] = 9999
    assert not led.verify()


def test_risk_higher_for_inactive_youth():
    youths, *_ = seed.build()
    rm = RiskModel()
    active = youths["y1"]
    active.activity_days = [seed.TODAY - i for i in range(10)]
    inactive = youths["y2"]
    inactive.activity_days = [seed.TODAY - 40 - i for i in range(15)]
    assert rm.score(inactive, seed.TODAY)["risk"] > rm.score(active, seed.TODAY)["risk"]


def test_levels_and_streak():
    assert level_for(0)["level"] == "Seedling"
    assert level_for(600)["level"] == "Changemaker"
    assert streak([10, 9, 8, 6]) == 3
