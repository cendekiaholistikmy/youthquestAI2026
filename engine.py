"""YouthQuest AI core engine.

Pure-Python (no heavy deps) so it runs unchanged on x86 and IBM LinuxONE (s390x).
Components:
  - QuestRecommender : hybrid content + collaborative scoring for personalised quests
  - RiskModel        : early-warning engagement/at-risk score (logistic model)
  - PointsLedger     : append-only, double-spend-safe XP / reward-points ledger
  - Gamification     : levels, badges, streaks, leaderboards
"""
from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CATEGORIES = ["environment", "education", "health", "community", "tech", "sports", "faith", "arts"]


# ---------------------------------------------------------------- data models
@dataclass
class Youth:
    id: str
    name: str
    age: int
    location: str
    interests: Dict[str, float]          # category -> 0..1
    skills: List[str] = field(default_factory=list)
    history: List[str] = field(default_factory=list)   # completed quest ids
    activity_days: List[int] = field(default_factory=list)  # unix day numbers of activity


@dataclass
class Quest:
    id: str
    title: str
    category: str
    location: str
    xp: int
    skills: List[str] = field(default_factory=list)
    organiser: str = ""


@dataclass
class Reward:
    id: str
    title: str
    cost: int
    partner: str
    stock: int


# ---------------------------------------------------------------- recommender
class QuestRecommender:
    """Hybrid recommender: interest match + skill growth + locality + peer signal + novelty."""

    W_INTEREST, W_SKILL, W_LOCAL, W_PEER, W_NOVEL = 0.40, 0.20, 0.15, 0.15, 0.10

    def __init__(self, youths: Dict[str, Youth], quests: Dict[str, Quest]):
        self.youths, self.quests = youths, quests

    @staticmethod
    def _cos(a: Dict[str, float], b: Dict[str, float]) -> float:
        dot = sum(a.get(k, 0) * b.get(k, 0) for k in CATEGORIES)
        na = math.sqrt(sum(v * v for v in a.values())) or 1
        nb = math.sqrt(sum(v * v for v in b.values())) or 1
        return dot / (na * nb)

    def _peer_score(self, y: Youth, q: Quest) -> float:
        """Share of similar youths (cosine > 0.7) who completed this quest."""
        peers = [p for p in self.youths.values() if p.id != y.id and self._cos(p.interests, y.interests) > 0.7]
        if not peers:
            return 0.0
        return sum(q.id in p.history for p in peers) / len(peers)

    def score(self, y: Youth, q: Quest) -> Dict[str, float]:
        interest = y.interests.get(q.category, 0.0)
        new_skills = [s for s in q.skills if s not in y.skills]
        skill = len(new_skills) / len(q.skills) if q.skills else 0.0
        local = 1.0 if q.location == y.location else 0.3
        peer = self._peer_score(y, q)
        done_cats = [self.quests[h].category for h in y.history if h in self.quests]
        novel = 1.0 - (done_cats.count(q.category) / len(done_cats)) if done_cats else 1.0
        total = (self.W_INTEREST * interest + self.W_SKILL * skill + self.W_LOCAL * local
                 + self.W_PEER * peer + self.W_NOVEL * novel)
        return {"total": round(total, 4), "interest": interest, "skill": round(skill, 2),
                "local": local, "peer": round(peer, 2), "novelty": round(novel, 2)}

    def recommend(self, youth_id: str, k: int = 5) -> List[dict]:
        y = self.youths[youth_id]
        ranked = []
        for q in self.quests.values():
            if q.id in y.history:
                continue
            s = self.score(y, q)
            ranked.append({"quest": q.__dict__, "score": s, "why": self.explain(s, q)})
        ranked.sort(key=lambda r: r["score"]["total"], reverse=True)
        return ranked[:k]

    @staticmethod
    def explain(s: Dict[str, float], q: Quest) -> str:
        reasons = []
        if s["interest"] >= 0.6:
            reasons.append(f"matches your interest in {q.category}")
        if s["skill"] >= 0.5:
            reasons.append("builds new skills")
        if s["local"] == 1.0:
            reasons.append("near you")
        if s["peer"] >= 0.3:
            reasons.append("popular with youths like you")
        return ", ".join(reasons) or "helps you explore something new"


# ---------------------------------------------------------------- risk model
class RiskModel:
    """Early-warning engagement risk (0..1). Logistic model over behaviour features.

    Weights are illustrative; in production they are trained on historical data and
    scored in-transaction on the IBM Z Telum on-chip AI accelerator.
    """

    BIAS = -1.2
    W = {"days_inactive": 0.12, "streak_broken": 0.9, "activity_drop": 1.6, "low_diversity": 0.5}

    def features(self, y: Youth, today: int) -> Dict[str, float]:
        days = sorted(y.activity_days)
        inactive = today - days[-1] if days else 60
        last30 = sum(1 for d in days if today - d < 30)
        prev30 = sum(1 for d in days if 30 <= today - d < 60)
        drop = max(0.0, (prev30 - last30) / prev30) if prev30 else 0.0
        streak_broken = 1.0 if inactive > 7 and prev30 > 0 else 0.0
        diversity = len({c for c, v in y.interests.items() if v > 0.4})
        return {"days_inactive": min(inactive, 60), "streak_broken": streak_broken,
                "activity_drop": round(drop, 2), "low_diversity": 1.0 if diversity <= 1 else 0.0}

    def score(self, y: Youth, today: Optional[int] = None) -> dict:
        today = today if today is not None else int(time.time() // 86400)
        f = self.features(y, today)
        z = self.BIAS + sum(self.W[k] * v for k, v in f.items())
        p = 1 / (1 + math.exp(-z))
        level = "high" if p >= 0.7 else "medium" if p >= 0.4 else "low"
        return {"risk": round(p, 3), "level": level, "features": f,
                "action": {"high": "Alert mentor for a personal check-in within 48h",
                           "medium": "Send personalised quest nudge + team invite",
                           "low": "Keep going"}[level]}


# ---------------------------------------------------------------- ledger
class InsufficientPoints(Exception):
    pass


class PointsLedger:
    """Append-only hash-chained ledger. Balance = sum of entries. Thread-safe, idempotent.

    On LinuxONE this maps to Db2 ACID transactions + pervasive encryption; the hash chain
    gives tamper evidence for auditors and sponsors.
    """

    def __init__(self):
        self._entries: List[dict] = []
        self._seen: set = set()
        self._lock = threading.Lock()

    def _append(self, youth_id: str, amount: int, reason: str, idem_key: str) -> dict:
        prev = self._entries[-1]["hash"] if self._entries else "GENESIS"
        body = f"{prev}|{youth_id}|{amount}|{reason}|{idem_key}"
        e = {"youth": youth_id, "amount": amount, "reason": reason, "key": idem_key,
             "prev": prev, "hash": hashlib.sha256(body.encode()).hexdigest()}
        self._entries.append(e)
        self._seen.add(idem_key)
        return e

    def balance(self, youth_id: str) -> int:
        return sum(e["amount"] for e in self._entries if e["youth"] == youth_id)

    def earned(self, youth_id: str) -> int:
        return sum(e["amount"] for e in self._entries if e["youth"] == youth_id and e["amount"] > 0)

    def credit(self, youth_id: str, amount: int, reason: str, idem_key: str) -> Optional[dict]:
        with self._lock:
            if idem_key in self._seen:          # duplicate check-in -> ignored
                return None
            return self._append(youth_id, amount, reason, idem_key)

    def debit(self, youth_id: str, amount: int, reason: str, idem_key: str) -> Optional[dict]:
        with self._lock:
            if idem_key in self._seen:
                return None
            if self.balance(youth_id) < amount:
                raise InsufficientPoints(f"{youth_id} has {self.balance(youth_id)} < {amount}")
            return self._append(youth_id, -amount, reason, idem_key)

    def verify(self) -> bool:
        prev = "GENESIS"
        for e in self._entries:
            body = f"{prev}|{e['youth']}|{e['amount']}|{e['reason']}|{e['key']}"
            if e["prev"] != prev or hashlib.sha256(body.encode()).hexdigest() != e["hash"]:
                return False
            prev = e["hash"]
        return True


# ---------------------------------------------------------------- gamification
LEVELS = [(0, "Seedling"), (200, "Sprout"), (500, "Changemaker"), (1000, "Trailblazer"),
          (2000, "Champion"), (4000, "Legend")]


def level_for(xp: int) -> dict:
    cur = LEVELS[0]
    nxt = None
    for i, (threshold, name) in enumerate(LEVELS):
        if xp >= threshold:
            cur = (threshold, name)
            nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    return {"level": cur[1], "xp": xp, "next": nxt[1] if nxt else None,
            "to_next": (nxt[0] - xp) if nxt else 0}


def streak(days: List[int]) -> int:
    s, ds = 0, sorted(set(days), reverse=True)
    for i, d in enumerate(ds):
        if i == 0 or ds[i - 1] - d == 1:
            s += 1
        else:
            break
    return s


def badges(y: Youth, quests: Dict[str, Quest]) -> List[str]:
    cats = [quests[h].category for h in y.history if h in quests]
    out = []
    if len(cats) >= 1:
        out.append("First Step")
    if len(cats) >= 5:
        out.append("Committed 5")
    if len(set(cats)) >= 4:
        out.append("All-Rounder")
    if cats.count("environment") >= 3:
        out.append("Green Guardian")
    if streak(y.activity_days) >= 7:
        out.append("7-Day Streak")
    return out


def leaderboard(youths: Dict[str, Youth], ledger: PointsLedger, location: Optional[str] = None) -> List[dict]:
    rows = [{"id": y.id, "name": y.name, "location": y.location, "xp": ledger.earned(y.id),
             "level": level_for(ledger.earned(y.id))["level"]}
            for y in youths.values() if location in (None, y.location)]
    rows.sort(key=lambda r: r["xp"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
