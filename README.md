# YouthQuest AI

**AI-personalised, gamified youth development platform on IBM LinuxONE.**
IBM Z Datathon 2026 · Wildcard: Beyond the Obvious

Youth earn XP and real-life rewards by completing volunteering and social-project "quests" picked for them by AI. Mentors get early warnings when a youth starts disengaging, so they can step in before he or she drifts toward social problems (drugs, vaping, gangsterism, online gambling).

![Quests](docs/screens/quests.png)

## Features
| | |
|---|---|
| 🎯 **AI quest recommender** | Hybrid scoring (interest, new skills, locality, peer signal, novelty) with a plain-language "why" |
| ✅ **Verified check-in** | Organiser QR token (+ GPS/photo in production); duplicate scans ignored |
| 🏆 **Gamification** | XP, 6 levels, badges, streaks, national / state leaderboards |
| 🎁 **Rewards marketplace** | Points redeemed for vouchers, transit passes, courses, internships, scholarships |
| 🔐 **Tamper-evident ledger** | Hash-chained, idempotent, double-spend-safe points ledger |
| 🚨 **Early-warning AI** | Logistic risk model over inactivity, activity drop, broken streaks, interest diversity |

## Quick start

**Web demo (no install):** open `web/index.html` in a browser (or enable GitHub Pages on `/web`). Switch users, check into quests, watch level/rank update, redeem rewards, open the Mentor tab.

**API:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --port 8080      # docs at http://localhost:8080/docs
pytest -q                         # 5 tests
```

| Endpoint | Purpose |
|---|---|
| `GET /youth/{id}` | Profile, level, points, streak, badges |
| `GET /youth/{id}/recommendations` | Personalised quests with explanations |
| `POST /checkin` | Verify QR and credit XP |
| `GET /rewards` · `POST /redeem` | Marketplace and atomic redemption |
| `GET /leaderboard?location=` | Rankings |
| `GET /youth/{id}/risk` · `GET /admin/at-risk` | Early-warning scores |
| `GET /health` | Includes ledger integrity check |

## IBM Z / LinuxONE
- **Pervasive encryption + Secure Execution + Crypto Express HSM** protect youth (incl. minors) personal data.
- **Telum on-chip AI accelerator** scores recommendations and risk in-transaction at check-in time.
- **Db2 ACID transactions** back the points ledger; the hash chain gives auditors and sponsors tamper evidence.
- **Red Hat OpenShift on LinuxONE**: `Dockerfile` builds for `linux/s390x`; `deploy/openshift.yaml` pins pods to s390x nodes with autoscaling 3→50.
- The prototype is pure Python so it runs unchanged on x86 or s390x; target deployment is IBM LinuxONE Community Cloud.

See [docs/architecture.md](docs/architecture.md).

## Structure
```
backend/  engine.py (recommender, risk, ledger, gamification) · app.py (FastAPI) · seed.py · test_engine.py
web/      index.html (standalone interactive demo)
deploy/   openshift.yaml
docs/     architecture.md, screens/
```

All demo data is synthetic. MIT licensed.
