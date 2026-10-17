"""Synthetic demo data (no real personal data)."""
import random
import time

from engine import CATEGORIES, PointsLedger, Quest, Reward, Youth

TODAY = int(time.time() // 86400)

QUESTS = [
    Quest("q1", "Beach clean-up at Santubong", "environment", "Kuching", 120, ["teamwork", "logistics"], "Green Sarawak"),
    Quest("q2", "Tutor primary kids in Maths", "education", "Kuching", 150, ["teaching", "communication"], "Cendekia"),
    Quest("q3", "Blood donation drive volunteer", "health", "Kuala Lumpur", 100, ["first-aid", "communication"], "MRC"),
    Quest("q4", "Food bank packing night", "community", "Kuching", 90, ["teamwork"], "Food Aid MY"),
    Quest("q5", "Build a website for a local NGO", "tech", "Remote", 250, ["coding", "design"], "Code4Good"),
    Quest("q6", "Coach futsal for at-risk teens", "sports", "Shah Alam", 180, ["leadership", "coaching"], "Sukan Komuniti"),
    Quest("q7", "Mosque community iftar crew", "faith", "Kuching", 110, ["logistics", "teamwork"], "HQ Mela Ju"),
    Quest("q8", "Mural painting for a rural school", "arts", "Bako", 160, ["design", "teamwork"], "Art Reach"),
    Quest("q9", "Mangrove planting", "environment", "Bako", 140, ["field-work"], "Green Sarawak"),
    Quest("q10", "Digital literacy class for seniors", "tech", "Kuching", 130, ["teaching", "coding"], "Code4Good"),
    Quest("q11", "Anti-vape peer ambassador training", "health", "Kuching", 200, ["public-speaking", "leadership"], "Youth Health"),
    Quest("q12", "Flood relief response team", "community", "Kuala Lumpur", 220, ["first-aid", "logistics"], "MERCY"),
]

REWARDS = [
    Reward("r1", "RM10 e-wallet voucher", 300, "Partner Bank", 500),
    Reward("r2", "Monthly transit pass", 600, "Rapid Transit", 200),
    Reward("r3", "Free online certification course", 800, "Coursera-style partner", 150),
    Reward("r4", "Internship interview fast-track", 1500, "Tech Corp CSR", 40),
    Reward("r5", "Scholarship application points", 3000, "Youth Foundation", 10),
    Reward("r6", "Futsal court 2-hour booking", 250, "Sukan Komuniti", 100),
]

NAMES = ["Aisyah", "Daniel", "Mei Ling", "Arjun", "Hafiz", "Nurul", "Jason", "Siti", "Kumar", "Farah",
         "Iskandar", "Lina", "Adam", "Priya", "Zul"]
LOCS = ["Kuching", "Kuala Lumpur", "Shah Alam", "Bako"]


def build(seed: int = 7):
    rnd = random.Random(seed)
    quests = {q.id: q for q in QUESTS}
    rewards = {r.id: r for r in REWARDS}
    youths, ledger = {}, PointsLedger()
    for i, n in enumerate(NAMES):
        interests = {c: round(rnd.random() ** 2, 2) for c in CATEGORIES}
        hist = rnd.sample(list(quests), rnd.randint(0, 6))
        days = sorted({TODAY - rnd.randint(0, 59) for _ in range(rnd.randint(2, 25))})
        if i % 5 == 4:  # some youths disengaging -> risk demo
            days = [d - 25 for d in days]
        y = Youth(f"y{i+1}", n, rnd.randint(15, 30), rnd.choice(LOCS), interests,
                  rnd.sample(["teamwork", "coding", "teaching", "design", "first-aid"], 2), hist, days)
        youths[y.id] = y
        for h in hist:
            ledger.credit(y.id, quests[h].xp, f"quest:{h}", f"{y.id}:{h}")
    return youths, quests, rewards, ledger
