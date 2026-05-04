from __future__ import annotations

import http.client
import json
import threading

import pytest

from oasis.aoasis.worker import (
    AOasisWorkerError,
    AOasisWorkerService,
    make_aoasis_worker_server,
)


def test_worker_service_runs_atherum_request_and_returns_result_contract(
    tmp_path,
):
    service = AOasisWorkerService(tmp_path, run_in_background=False)

    started = service.start_simulation(_worker_request("run-001-twitter"))
    result = service.get_result("run-001-twitter")

    assert started == {
        "simulationId": "run-001-twitter",
        "status": "completed",
    }
    assert result["simulationId"] == "run-001-twitter"
    assert result["status"] == "completed"
    assert result["propagation"][0]["topComments"]
    assert result["timeline"]
    assert result["network"]["nodes"]
    assert result["network"]["communities"]
    assert result["metadata"]["runner"] == "aoasis"
    assert result["metadata"]["variant"] == "A-Oasis"
    assert result["metadata"]["oasisEvents"]
    assert result["metadata"]["agentContexts"][0]["societyCore"][
        "societyAgentId"
    ] == "soc_001"


def test_worker_service_reports_selected_runtime(tmp_path):
    service = AOasisWorkerService(
        tmp_path,
        run_in_background=False,
        runtime_mode="oasis-manual",
    )

    assert service.health()["runtime"] == "oasis-manual"


def test_worker_service_can_run_real_oasis_manual_runtime(tmp_path):
    service = AOasisWorkerService(
        tmp_path,
        run_in_background=False,
        runtime_mode="oasis-manual",
    )

    started = service.start_simulation(
        _worker_request("run-oasis-manual-reddit", "reddit"))
    result = service.get_result("run-oasis-manual-reddit")

    assert started == {
        "simulationId": "run-oasis-manual-reddit",
        "status": "completed",
    }
    assert result["status"] == "completed"
    assert result["propagation"][0]["topComments"]
    assert result["timeline"]
    assert result["network"]["nodes"]
    assert result["metadata"]["runner"] == "aoasis-oasis-manual"
    assert result["metadata"]["oasisEvents"]
    assert result["metadata"]["oasisEvents"][0]["metadata"][
        "source"] == "oasis-output"
    assert result["metadata"]["agentContexts"][0]["societyCore"][
        "societyAgentId"
    ] == "soc_001"


def test_worker_service_exposes_llm_runtime_configuration_errors(tmp_path):
    service = AOasisWorkerService(
        tmp_path,
        run_in_background=False,
        runtime_mode="oasis-llm",
    )

    started = service.start_simulation(_worker_request("run-oasis-llm-twitter"))
    assert started == {
        "simulationId": "run-oasis-llm-twitter",
        "status": "failed",
    }
    with pytest.raises(AOasisWorkerError) as error:
        service.get_result("run-oasis-llm-twitter")

    assert error.value.status_code == 500
    assert "requires a model backend" in error.value.detail


def test_worker_service_rejects_duplicate_simulation_ids(tmp_path):
    service = AOasisWorkerService(tmp_path, run_in_background=False)
    service.start_simulation(_worker_request("run-duplicate-twitter"))

    with pytest.raises(AOasisWorkerError) as error:
        service.start_simulation(_worker_request("run-duplicate-twitter"))

    assert error.value.status_code == 400
    assert "already exists" in error.value.detail


def test_worker_http_server_matches_atherum_routes(tmp_path):
    service = AOasisWorkerService(tmp_path, run_in_background=False)
    server = make_aoasis_worker_server(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection(
            server.server_address[0],
            server.server_address[1],
            timeout=10,
        )
        conn.request("GET", "/health")
        health = conn.getresponse()
        assert health.status == 200
        assert json.loads(health.read())["status"] == "ok"

        body = json.dumps(_worker_request("run-http-reddit", "reddit"))
        conn.request(
            "POST",
            "/api/v1/simulations",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        started = conn.getresponse()
        assert started.status == 200
        assert json.loads(started.read())["simulationId"] == "run-http-reddit"

        conn.request("GET", "/api/v1/simulations/run-http-reddit/result")
        result = conn.getresponse()
        assert result.status == 200
        assert json.loads(result.read())["status"] == "completed"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _worker_request(simulation_id: str, platform: str = "twitter"):
    return {
        "id": simulation_id,
        "workspaceId": "workspace-sneaker",
        "privateContext": "Use the uploaded creative as private context.",
        "modelName": "google/gemini-3.1-flash-lite-preview",
        "platform": {
            "platform": platform,
            "agentCount": 4,
            "durationHours": 1,
            "timeCompression": 3600,
            "recsAlgorithm": "engagement-weighted",
        },
        "seed": {
            "content": [
                {
                    "type": "post",
                    "text": "New sneaker creative with wave motif. Would people share or buy?",
                    "mediaUrls": ["https://assets.example/shoe.jpg"],
                    "injectAtHour": 0,
                }
            ]
        },
        "personas": [
            {
                "personaId": "soc_001",
                "name": "Ari",
                "archetype": "skeptical buyer",
                "personalityPrompt": "Checks product claims and asks for warranty proof.",
                "behaviorTraits": {
                    "societyCore": {
                        "societyAgentId": "soc_001",
                        "societyAgentKey": "buyer_001",
                        "modeRole": "Skeptical buyer",
                        "memoryHandle": {
                            "namespace": "workspaceAgentMemories",
                            "ref": "workspace-sneaker:soc_001",
                        },
                    },
                    "traits": ["risk-sensitive", "price-aware"],
                    "interests": ["durability", "pricing"],
                    "dislikes": ["vague claims"],
                    "trustNeeds": ["warranty", "material proof"],
                    "socialGroups": ["value-seeking buyers"],
                },
            },
            {
                "personaId": "soc_002",
                "name": "Mei",
                "archetype": "visual amplifier",
                "personalityPrompt": "Shares polished product drops when the visual hook lands.",
                "behaviorTraits": {
                    "societyCore": {
                        "societyAgentId": "soc_002",
                        "societyAgentKey": "visual_002",
                        "modeRole": "Visual amplifier",
                        "memoryHandle": {
                            "namespace": "workspaceAgentMemories",
                            "ref": "workspace-sneaker:soc_002",
                        },
                    },
                    "traits": ["aesthetic", "novelty-seeking"],
                    "interests": ["visual polish", "limited drops"],
                    "dislikes": ["generic product shots"],
                    "trustNeeds": ["brand specificity"],
                    "socialGroups": ["early visual adopters"],
                },
            },
        ],
        "backgroundAgentCount": 0,
        "costBudgetUsd": 1,
    }
