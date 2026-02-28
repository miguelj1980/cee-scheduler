from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pandas as pd
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from conflict_engine import calculate_conflicts

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local testing; we can tighten this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (including index.html if needed)
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    here = os.path.dirname(__file__)
    index_path = os.path.join(here, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()
    
# --------- Load data once at startup ---------

students = pd.read_csv("synthetic_students_400.csv")
# student_plans = pd.read_csv("synthetic_student_plans_400_fall2026.csv")
student_plans = pd.read_csv("synthetic_student_plans_400_2026_27.csv")
timeslots = pd.read_csv("cee_timeslots_config.csv")
courses_all = pd.read_csv("cee_course_offerings_2026_27_ug.csv")

# For now, we’ll attach a term to all courses if not present
if "term" not in courses_all.columns:
    courses_all["term"] = "2026FA"


# --------- API models ---------

class ScheduledOffering(BaseModel):
    course_code: str
    day_pattern: str
    start_time: str
    end_time: str
    term: str


# --------- API endpoints ---------

@app.get("/timeslots")
def get_timeslots():
    """
    Return the list of allowed time slots (MW, WF, MF, TR patterns).
    """
    return timeslots.to_dict(orient="records")


@app.get("/courses")
def get_courses(term: str = "2026FA"):
    """
    Return undergrad CEE courses for a given term.
    """
    df = courses_all[courses_all["term"] == term]
    return df.to_dict(orient="records")


@app.post("/conflicts")
def compute_conflicts(schedule: List[ScheduledOffering]):
    """
    Compute conflict metrics for a given schedule.

    Body: list of objects with
      - course_code
      - day_pattern (MW, WF, MF, TR)
      - start_time (HH:MM)
      - end_time (HH:MM)
      - term (e.g., 2026FA)
    """
    if not schedule:
        return {
            "term": [],
            "total_students": len(students),
            "courses_in_schedule": 0,
            "metrics": {
                "expected_conflicts_all": 0.0,
                "students_with_conflict": 0,
                "conflict_rate_overall": 0.0,
                "by_path_type": [],
                "top_conflicting_pairs": [],
                "top_conflicting_courses": [],
            },
        }

    schedule_df = pd.DataFrame([s.dict() for s in schedule])
    results = calculate_conflicts(schedule_df, student_plans, students)
    return results


@app.get("/")
def root():
    """
    Simple health check.
    """
    return {"status": "ok", "message": "CEE scheduling conflict API is running"}
