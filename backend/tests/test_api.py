import os
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="datawise-api-test-"))
DB = TEST_ROOT / "test.db"
UPLOADS = TEST_ROOT / "uploads"
os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
os.environ["STORAGE_PATH"] = str(UPLOADS)
os.environ["AI_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_project_upload_profile_and_analysis_flow(client):
    project = client.post("/api/v1/projects", json={"name": "Test project"})
    assert project.status_code == 201
    pid = project.json()["id"]
    opened = client.get(f"/api/v1/projects/{pid}")
    assert opened.status_code == 200 and opened.json()["datasets"] == []
    uploaded = client.post(
        f"/api/v1/projects/{pid}/datasets",
        files={"file": ("sales.csv", b"category,revenue\nA,10\nB,20\nA,30\n", "text/csv")},
    )
    assert uploaded.status_code == 201
    dataset = uploaded.json()
    assert dataset["profile"]["row_count"] == 3
    analysis = client.post(
        f"/api/v1/datasets/{dataset['id']}/analysis",
        json={"question": "top 2 categories by revenue"},
    )
    assert analysis.status_code == 200
    assert analysis.json()["result"][0]["value"] == 40
    messages = client.get(f"/api/v1/conversations/{analysis.json()['conversation_id']}/messages")
    assert messages.status_code == 200 and len(messages.json()) == 2


def test_reject_unsupported_file_and_missing_project(client):
    assert (
        client.post(
            "/api/v1/projects/nope/datasets", files={"file": ("notes.txt", b"x", "text/plain")}
        ).status_code
        == 404
    )
    project = client.post("/api/v1/projects", json={"name": "Upload test"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("notes.txt", b"x", "text/plain")},
    )
    assert response.status_code == 415


def test_followup_uses_prior_monthly_analysis(client):
    project = client.post("/api/v1/projects", json={"name": "Time series"}).json()
    csv = b"date,region,revenue\n2025-01-03,West,100\n2025-01-10,East,50\n2025-02-03,West,50\n2025-02-10,East,45\n"
    dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets", files={"file": ("trend.csv", csv, "text/csv")}
    ).json()
    first = client.post(
        f"/api/v1/datasets/{dataset['id']}/analysis", json={"question": "Plot monthly revenue"}
    ).json()
    follow = client.post(
        f"/api/v1/datasets/{dataset['id']}/analysis",
        json={
            "question": "Which region contributed most to the decline?",
            "conversation_id": first["conversation_id"],
        },
    )
    assert follow.status_code == 200
    assert follow.json()["analysis_type"] == "follow_up"
    assert "West" in follow.json()["answer"]


def test_named_project_creation_trims_name_and_rejects_blank(client):
    response = client.post("/api/v1/projects", json={"name": "  Demo project  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Demo project"
    assert client.post("/api/v1/projects", json={"name": "   "}).status_code == 422


def test_delete_empty_project(client):
    project = client.post("/api/v1/projects", json={"name": "Empty project"}).json()
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 404


def test_delete_project_cascades_datasets_conversation_and_upload(client):
    from app.db import SessionLocal
    from app.models import AnalysisResult, AnalysisSession, Dataset
    from app.storage import LocalStorage

    project = client.post("/api/v1/projects", json={"name": "Delete populated project"}).json()
    dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("sales.csv", b"revenue\n10\n20\n", "text/csv")},
    ).json()
    analysis = client.post(
        f"/api/v1/datasets/{dataset['id']}/analysis", json={"question": "total revenue"}
    ).json()
    db = SessionLocal()
    try:
        stored = db.get(Dataset, dataset["id"]).storage_key
        analysis_session = db.query(AnalysisSession).filter_by(conversation_id=analysis["conversation_id"]).one()
        session_id = analysis_session.id
        result_id = analysis_session.result.id
    finally:
        db.close()
    stored_path = LocalStorage().path(stored)
    assert stored_path.exists()

    response = client.delete(f"/api/v1/projects/{project['id']}")
    assert response.status_code == 204
    assert not stored_path.exists()
    assert client.get(f"/api/v1/datasets/{dataset['id']}").status_code == 404
    assert client.get(f"/api/v1/conversations/{analysis['conversation_id']}/messages").status_code == 404
    db = SessionLocal()
    try:
        assert db.get(AnalysisSession, session_id) is None
        assert db.get(AnalysisResult, result_id) is None
    finally:
        db.close()
