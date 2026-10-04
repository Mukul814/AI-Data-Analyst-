import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.ai.provider import create_provider
from app.analysis.profile import profile_dataframe
from app.core.config import get_settings
from app.db import Base, engine, get_db
from app.execution.runner import execute_analysis
from app.ingestion import parse_dataset
from app.models import (
    AnalysisResult,
    AnalysisSession,
    Conversation,
    Dataset,
    DatasetColumn,
    Message,
    Project,
)
from app.schemas import AnalysisResponse, AskRequest, ProjectCreate
from app.storage import LocalStorage


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        payload = {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        for key in (
            "request_id",
            "dataset_id",
            "analysis_id",
            "duration_ms",
            "status_code",
            "path",
            "method",
            "provider",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


handler = logging.StreamHandler()
handler.setFormatter(JsonLogFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger("analyst")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AI Data Analyst API", version="1.0.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request, call_next):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info(
        "request_complete",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        },
    )
    return response


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "ai_provider": get_settings().ai_provider}


@app.get("/api/v1/projects")
def list_projects(db: Session = Depends(get_db)):
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "created_at": p.created_at.isoformat(),
            "datasets": [
                {
                    "id": d.id,
                    "project_id": d.project_id,
                    "filename": d.filename,
                    "profile": d.profile,
                    "created_at": d.created_at.isoformat(),
                }
                for d in p.datasets
            ],
        }
        for p in db.query(Project).order_by(Project.created_at.desc()).all()
    ]


@app.post("/api/v1/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name.strip(), description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at.isoformat(),
        "datasets": [],
    }


@app.post("/api/v1/projects/{project_id}/datasets", status_code=201)
async def upload_dataset(
    project_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in {".csv", ".xlsx"}:
        raise HTTPException(415, "Upload a CSV or XLSX file.")
    limit = get_settings().max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, "File exceeds the upload size limit.")
    try:
        frame = await run_in_threadpool(parse_dataset, filename, content)
        profile = await run_in_threadpool(profile_dataframe, frame)
        key = await run_in_threadpool(LocalStorage().save, filename, content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        log.exception("Dataset ingestion failed")
        raise HTTPException(500, "Dataset could not be stored.") from exc
    dataset = Dataset(project_id=project.id, filename=filename, storage_key=key, profile=profile)
    db.add(dataset)
    db.flush()
    for column in profile["columns"]:
        db.add(
            DatasetColumn(
                dataset_id=dataset.id,
                name=column["name"],
                dtype=column["dtype"],
                semantic_type=column["semantic_type"],
                details=column,
            )
        )
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        try:
            LocalStorage().delete(key)
        except Exception:
            log.exception("Could not remove orphaned dataset file")
        log.exception("Dataset metadata persistence failed")
        raise HTTPException(500, "Dataset could not be saved.") from exc
    db.refresh(dataset)
    return {
        "id": dataset.id,
        "project_id": dataset.project_id,
        "filename": dataset.filename,
        "profile": dataset.profile,
        "created_at": dataset.created_at.isoformat(),
    }


@app.get("/api/v1/datasets/{dataset_id}")
def get_dataset(dataset_id: str, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found.")
    return {
        "id": dataset.id,
        "project_id": dataset.project_id,
        "filename": dataset.filename,
        "profile": dataset.profile,
        "created_at": dataset.created_at.isoformat(),
    }


@app.post("/api/v1/datasets/{dataset_id}/analysis", response_model=AnalysisResponse)
async def ask(dataset_id: str, payload: AskRequest, db: Session = Depends(get_db)):
    started = time.perf_counter()
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found.")
    conversation = (
        db.get(Conversation, payload.conversation_id) if payload.conversation_id else None
    )
    if payload.conversation_id and conversation is None:
        raise HTTPException(404, "Conversation not found.")
    if conversation and conversation.dataset_id != dataset_id:
        raise HTTPException(400, "Conversation belongs to another dataset.")
    if conversation is None:
        conversation = Conversation(dataset_id=dataset_id, title=payload.question[:120])
        db.add(conversation)
        db.flush()
    try:
        file_bytes = await run_in_threadpool(LocalStorage().path(dataset.storage_key).read_bytes)
        frame = await run_in_threadpool(parse_dataset, dataset.filename, file_bytes)
        prev = (
            db.query(AnalysisSession)
            .filter(AnalysisSession.conversation_id == conversation.id)
            .order_by(AnalysisSession.created_at.desc())
            .first()
        )
        previous = prev.result.payload if prev and prev.result else None
        rows = json.loads(frame.to_json(orient="records", date_format="iso"))
        analysis = await run_in_threadpool(
            execute_analysis, rows, [str(c) for c in frame.columns], payload.question, previous
        )
        provider = create_provider()
        result_for_ai = (
            analysis["result"]
            if isinstance(analysis["result"], dict)
            else {"rows": analysis["result"]}
        )
        analysis["answer"] = await asyncio.wait_for(
            provider.explain(payload.question, analysis["answer"], result_for_ai),
            timeout=get_settings().ai_request_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(504, "Analysis or AI provider timed out. Please try again.") from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        log.exception("Analysis failed", extra={"dataset_id": dataset_id})
        raise HTTPException(
            502, "Analysis could not be completed. Please try a clearer question."
        ) from exc
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.question))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=analysis["answer"]))
    session = AnalysisSession(conversation_id=conversation.id, status="completed")
    db.add(session)
    db.flush()
    db.add(AnalysisResult(session_id=session.id, payload=analysis, code=analysis.get("code")))
    db.commit()
    log.info(
        "analysis_complete",
        extra={
            "analysis_id": session.id,
            "dataset_id": dataset.id,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "provider": get_settings().ai_provider,
        },
    )
    return {"conversation_id": conversation.id, **analysis}


@app.get("/api/v1/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, db: Session = Depends(get_db)):
    if not db.get(Conversation, conversation_id):
        raise HTTPException(404, "Conversation not found.")
    return [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in db.query(Message)
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at)
        .all()
    ]
