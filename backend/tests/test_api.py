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
