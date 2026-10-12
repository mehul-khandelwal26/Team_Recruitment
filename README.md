# Team Recruitment Automation Tool

Configurable and explainable hackathon team shortlisting system.

---

## 🎯 Problem

Hackathon organizers receive hundreds of team registrations and need to **shortlist the top X teams** fairly and transparently. Manual review is slow, inconsistent, and opaque. This tool automates the process with configurable eligibility rules, weighted scoring, and human-readable explanations for every decision.

## ✨ Key Features (Planned)

- **CSV / JSON ingestion** – upload registration data in common formats.
- **Variable team sizes** – handle teams of any size without hard-coded limits.
- **Configurable eligibility rules** – define pass/fail criteria (e.g. minimum experience, required skills).
- **Weighted scoring engine** – assign weights to different evaluation signals.
- **Missing-data handling** – gracefully score teams even when some member profiles are incomplete.
- **Transparent explanations** – every score comes with a plain-English breakdown.
- **Top-N ranking** – select the best X teams with tie-breaking support.
- **Export** – download results as CSV or JSON.
- **Web dashboard** – React frontend for organizers to configure, review, and export.

## 🛠️ Technology Stack

| Layer     | Technology                       |
| --------- | -------------------------------- |
| Backend   | Python · FastAPI · Pydantic      |
| Server    | Uvicorn                          |
| Data      | Pandas                           |
| Frontend  | React + Vite *(planned)*         |
| Database  | PostgreSQL *(planned)*           |

## 📐 High-Level Processing Workflow

```
Registration Data (CSV/JSON)
        │
        ▼
   ┌──────────┐
   │ Ingestion │  ──▶  Parse & normalise raw data
   └──────────┘
        │
        ▼
   ┌────────────┐
   │ Validation  │  ──▶  Data-quality & completeness checks
   └────────────┘
        │
        ▼
   ┌──────────────┐
   │ Signal Extraction │  ──▶  Derive scoring signals per member
   └──────────────┘
        │
        ▼
   ┌────────────────┐
   │ Eligibility Rules │  ──▶  Apply configurable pass/fail criteria
   └────────────────┘
        │
        ▼
   ┌─────────┐
   │ Scoring  │  ──▶  Weighted scoring per member
   └─────────┘
        │
        ▼
   ┌─────────────┐
   │ Aggregation  │  ──▶  Combine member scores → team score
   └─────────────┘
        │
        ▼
   ┌─────────┐
   │ Ranking  │  ──▶  Sort & select top X teams
   └─────────┘
        │
        ▼
   ┌─────────────┐
   │ Explanation  │  ──▶  Generate human-readable score breakdowns
   └─────────────┘
        │
        ▼
   ┌────────┐
   │ Export  │  ──▶  CSV / JSON download
   └────────┘
```

## 📦 Current Implementation Status

| Component            | Status          |
| -------------------- | --------------- |
| Project structure    | ✅ Done          |
| FastAPI app skeleton | ✅ Done          |
| Health-check endpoint| ✅ Done          |
| CORS configuration   | ✅ Done          |
| App configuration    | ✅ Done          |
| Data ingestion       | 🔲 Not started  |
| Validation           | 🔲 Not started  |
| Signal extraction    | 🔲 Not started  |
| Eligibility rules    | 🔲 Not started  |
| Scoring engine       | 🔲 Not started  |
| Aggregation          | 🔲 Not started  |
| Ranking              | 🔲 Not started  |
| Explanations         | 🔲 Not started  |
| Export (CSV/JSON)    | 🔲 Not started  |
| Database models      | 🔲 Not started  |
| React frontend       | 🔲 Not started  |

## 🚀 Getting Started

### Prerequisites

- Python 3.10+

### Backend Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the virtual environment
#    Windows (PowerShell):
.\venv\Scripts\Activate.ps1
#    Windows (cmd):
venv\Scripts\activate.bat
#    macOS / Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Copy and customise environment config
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux

# 6. Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at **http://localhost:8000**.

- **Interactive API docs (Swagger):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/api/health

## 🗺️ Next Development Milestones

1. **Data ingestion** – CSV/JSON upload endpoint with Pandas parsing.
2. **Pydantic schemas** – request/response models for teams and members.
3. **Eligibility rules engine** – configurable pass/fail criteria.
4. **Weighted scoring** – per-member signal scoring with configurable weights.
5. **Aggregation & ranking** – team-level scores and top-N selection.
6. **Explanations** – human-readable score breakdowns.
7. **Export** – CSV/JSON download of shortlisted teams.
8. **React frontend** – initialise with Vite, build organizer dashboard.
9. **Database integration** – PostgreSQL persistence.

## 📄 License

This project is for educational / hackathon use.
