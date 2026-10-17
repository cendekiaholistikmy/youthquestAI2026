"""YouthQuest AI REST API (FastAPI). Run: uvicorn app:app --host 0.0.0.0 --port 8080"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import seed
from engine import (InsufficientPoints, QuestRecommender, RiskModel, badges, leaderboard,
                    level_for, streak)

app = FastAPI(title="YouthQuest AI", version="0.1.0",
              description="AI-personalised gamified youth development platform")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

YOUTHS, QUESTS, REWARDS, LEDGER = seed.build()
RECO = QuestRecommender(YOUTHS, QUESTS)
RISK = RiskModel()


class CheckIn(BaseModel):
    youth_id: str
    quest_id: str
    qr_token: str          # issued by organiser at the venue
    lat: float | None = None
    lon: float | None = None


class Redeem(BaseModel):
    youth_id: str
    reward_id: str
    request_id: str        # idempotency key from the client


def _youth(yid: str):
    if yid not in YOUTHS:
        raise HTTPException(404, "youth not found")
    return YOUTHS[yid]


@app.get("/health")
def health():
    return {"ok": True, "ledger_intact": LEDGER.verify()}


@app.get("/youth/{yid}")
def profile(yid: str):
    y = _youth(yid)
    xp = LEDGER.earned(yid)
    return {"youth": y.__dict__, "points": LEDGER.balance(yid), **level_for(xp),
            "streak": streak(y.activity_days), "badges": badges(y, QUESTS)}


@app.get("/youth/{yid}/recommendations")
def recommendations(yid: str, k: int = 5):
    _youth(yid)
    return RECO.recommend(yid, k)


@app.get("/youth/{yid}/risk")
def risk(yid: str):
    return RISK.score(_youth(yid), seed.TODAY)


@app.post("/checkin")
def checkin(c: CheckIn):
    y = _youth(c.youth_id)
    q = QUESTS.get(c.quest_id) or (_ for _ in ()).throw(HTTPException(404, "quest not found"))
    if c.qr_token != f"QR-{q.id}":                 # demo verification rule
        raise HTTPException(400, "invalid QR token")
    entry = LEDGER.credit(y.id, q.xp, f"quest:{q.id}", f"{y.id}:{q.id}")
    if entry is None:
        return {"status": "duplicate", "points": LEDGER.balance(y.id)}
    y.history.append(q.id)
    y.activity_days.append(seed.TODAY)
    return {"status": "ok", "xp_gained": q.xp, "points": LEDGER.balance(y.id),
            **level_for(LEDGER.earned(y.id)), "badges": badges(y, QUESTS)}


@app.get("/rewards")
def rewards():
    return [r.__dict__ for r in REWARDS.values()]


@app.post("/redeem")
def redeem(r: Redeem):
    _youth(r.youth_id)
    rw = REWARDS.get(r.reward_id)
    if not rw or rw.stock <= 0:
        raise HTTPException(409, "reward unavailable")
    try:
        e = LEDGER.debit(r.youth_id, rw.cost, f"reward:{rw.id}", r.request_id)
    except InsufficientPoints as ex:
        raise HTTPException(402, str(ex))
    if e is None:
        return {"status": "duplicate"}
    rw.stock -= 1
    return {"status": "ok", "voucher": f"YQ-{e['hash'][:10].upper()}", "points": LEDGER.balance(r.youth_id)}


@app.get("/leaderboard")
def board(location: str | None = None):
    return leaderboard(YOUTHS, LEDGER, location)


@app.get("/admin/at-risk")
def at_risk():
    rows = [{"id": y.id, "name": y.name, **RISK.score(y, seed.TODAY)} for y in YOUTHS.values()]
    return sorted([r for r in rows if r["level"] != "low"], key=lambda r: -r["risk"])
