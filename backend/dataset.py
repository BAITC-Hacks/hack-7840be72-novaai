"""Strict adapter for the documented demo schema; no implicit coercion."""
import csv
import io
import json
from datetime import date
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, AfterValidator
from typing import Annotated, Literal

Level = Annotated[int, Field(strict=True, ge=0, le=5)]
Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")]
Grade = Literal["Junior", "Middle", "Senior", "Lead"]

def iso_date(value):
    if date.fromisoformat(value).isoformat()!=value: raise ValueError('Expected YYYY-MM-DD')
    return value
Day = Annotated[str, AfterValidator(iso_date)]

class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Employee(Model):
    employee_id: Identifier
    role: Annotated[str, Field(min_length=1, max_length=120)]
    grade: Grade
    tenure_months: Annotated[int, Field(ge=0, le=1200)]
    skills: dict[Identifier, Level]
    as_of_date: Day | None = None
    career_goal: dict[str, str] | None = None

class Gain(Model):
    gain: Annotated[int, Field(ge=1, le=5)]
    max_level: Level

class Event(Model):
    mandatory: bool = False
    due_date: Day | None = None

    @field_validator("due_date")
    @classmethod
    def valid_due_date(cls, value):
        if value is not None:
            parsed=date.fromisoformat(value)
            if parsed.isoformat()!=value: raise ValueError("Expected YYYY-MM-DD")
        return value

    id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=500)]
    type: Annotated[str, Field(min_length=1, max_length=120)]
    target_audience: Annotated[list[str], Field(min_length=1)]
    skill_gains: dict[Identifier, Gain]
    format: str | None = None
    target_grades: list[Grade] = Field(default_factory=list)
    prerequisites: dict[Identifier, Level] = Field(default_factory=dict)
    upcoming_sessions: list[Day] | None = None
    repeatable: bool = False

class Skill(Model):
    requirements: dict[Grade, Level]
    role_requirements: dict[str, dict[Grade, Level]] = Field(default_factory=dict)
    role_criticality: dict[str, dict[Grade, Annotated[int, Field(ge=1, le=10)]]] = Field(default_factory=dict)
    name: str | None = None
    criticality: dict[Grade, Annotated[int, Field(ge=1, le=10)]] = Field(default_factory=dict)

class History(Model):
    recommended: bool = False
    employee_id: Identifier
    event_id: Identifier
    status: Literal["completed", "skipped", "declined", "in_progress", "dropped", "no_show", "overdue"]
    due_date: Day | None = None
    assigned_by: Literal["self", "manager", "hr"] | None = None
    record_id: str | None = None
    date: Day

class Dataset(Model):
    as_of_date: Day | None = None
    employees: Annotated[list[Employee], Field(min_length=1, max_length=10000)]
    events: Annotated[list[Event], Field(max_length=5000)]
    skills: Annotated[dict[Identifier, Skill], Field(min_length=1, max_length=1000)]
    history: Annotated[list[History], Field(max_length=200000)]

class DatasetError(ValueError):
    def __init__(self, errors):
        self.errors = errors[:50]
        super().__init__("Dataset validation failed")

FILES = {"employees.json", "events.json", "skills.json", "activity_history.csv"}
MAX_BYTES = 12 * 1024 * 1024


def validate(raw):
    try:
        result = Dataset.model_validate(raw).model_dump()
    except ValidationError as error:
        raise DatasetError([{"path": ".".join(map(str,e["loc"])), "message": e["msg"]} for e in error.errors()]) from error
    errors = []
    def issue(path, message):
        if len(errors) < 50: errors.append({"path": path, "message": message})
    for collection, key in [("employees", "employee_id"), ("events", "id")]:
        seen = set()
        for i, item in enumerate(result[collection]):
            if item[key] in seen: issue(f"{collection}.{i}.{key}", "Duplicate identifier")
            seen.add(item[key])
    employees = {e["employee_id"]: e for e in result["employees"]}
    events = {e["id"]: e for e in result["events"]}
    for collection, key in [("employees", "skills"), ("events", "skill_gains")]:
        for i, item in enumerate(result[collection]):
            for skill in item[key]:
                if skill not in result["skills"]: issue(f"{collection}.{i}.{key}.{skill}", "Unknown skill")
    for i, event in enumerate(result['events']):
        if not event['mandatory'] and not event['skill_gains']:
            issue(f'events.{i}.skill_gains', 'Voluntary activity needs skill gains')
        for skill in event['prerequisites']:
            if skill not in result['skills']: issue(f'events.{i}.prerequisites', 'Unknown skill')
        for value in event['upcoming_sessions'] or []:
            try:
                if date.fromisoformat(value).isoformat()!=value: raise ValueError()
            except ValueError: issue(f'events.{i}.upcoming_sessions', 'Expected YYYY-MM-DD')
    seen_history = set()
    for i, row in enumerate(result["history"]):
        if row["employee_id"] not in employees: issue(f"history.{i}.employee_id", "Unknown employee")
        if row["event_id"] not in events: issue(f"history.{i}.event_id", "Unknown event")
        try:
            parsed = date.fromisoformat(row["date"])
            if parsed.isoformat() != row["date"]: raise ValueError()
        except ValueError: issue(f"history.{i}.date", "Expected date YYYY-MM-DD")
        signature = tuple(row.values())
        if signature in seen_history: issue(f"history.{i}", "Duplicate history row")
        seen_history.add(signature)
    if errors: raise DatasetError(errors)
    return result


def parse_files(files):
    if set(files) != FILES:
        raise DatasetError([{"path": "files", "message": "Provide exactly employees.json, events.json, skills.json, activity_history.csv"}])
    if sum(len(v.encode("utf-8")) for v in files.values()) > MAX_BYTES:
        raise DatasetError([{"path":"files", "message":"Dataset exceeds 12 MiB"}])
    def unique_object(pairs):
        value = {}
        for k,v in pairs:
            if k in value: raise ValueError("Duplicate JSON key")
            value[k] = v
        return value
    raw = {}
    for filename in ["employees.json", "events.json", "skills.json"]:
        try:
            raw[filename[:-5]] = json.loads(files[filename].lstrip("\ufeff"), object_pairs_hook=unique_object)
        except (ValueError, RecursionError):
            raise DatasetError([{"path": filename, "message": "Invalid JSON or duplicate key"}])
    if isinstance(raw['employees'], dict) and 'employees' in raw['employees']:
        from .official import adapt
        return validate(adapt(raw, files['activity_history.csv']))
    try:
        reader = csv.DictReader(io.StringIO(files["activity_history.csv"].lstrip("\ufeff")), strict=True)
        if reader.fieldnames not in (["employee_id", "event_id", "status", "date"], ["employee_id", "event_id", "status", "date", "recommended"]):
            raise ValueError("CSV header must be employee_id,event_id,status,date")
        raw["history"] = list(reader)
        for row in raw["history"]:
            if "recommended" in row:
                if row["recommended"] not in {"true","false"}: raise ValueError("recommended must be true or false")
                row["recommended"]=row["recommended"]=="true"
    except (ValueError, csv.Error) as error:
        raise DatasetError([{"path":"activity_history.csv", "message":str(error)}])
    return validate(raw)


def load_directory(path):
    return parse_files({name:(Path(path)/name).read_text(encoding="utf-8-sig") for name in FILES})
