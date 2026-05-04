from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from oasis.aoasis.cost import estimate_run_cost
from oasis.aoasis.run_config import AOasisRunConfig
from oasis.atherum import AOASIS_VARIANT_NAME


class AOasisWorkerError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class AOasisWorkerService:
    """Atherum-compatible local worker around the A-Oasis runtime contract."""

    def __init__(self, root_dir: str | Path, run_in_background: bool = True):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.run_in_background = run_in_background
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, Any]] = {}

    def health(self) -> dict[str, str]:
        return {
            "status": "ok",
            "variant": AOASIS_VARIANT_NAME,
        }

    def start_simulation(self, request: dict[str, Any]) -> dict[str, str]:
        simulation_id = _required_string(request, "id")
        with self._lock:
            if simulation_id in self._runs:
                raise AOasisWorkerError(
                    400, f"Simulation {simulation_id} already exists")
            self._runs[simulation_id] = {
                "status": "running",
                "request": request,
                "result": None,
                "error": None,
            }

        if self.run_in_background:
            thread = threading.Thread(
                target=self._complete_simulation,
                args=(simulation_id, ),
                daemon=True,
            )
            thread.start()
            status = "running"
        else:
            self._complete_simulation(simulation_id)
            status = "completed"

        return {
            "simulationId": simulation_id,
            "status": status,
        }

    def get_result(self, simulation_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._runs.get(simulation_id)
            if run is None:
                raise AOasisWorkerError(
                    404, f"Simulation {simulation_id} was not found")
            status = run["status"]
            result = run["result"]
            error = run["error"]

        if status == "running":
            raise AOasisWorkerError(409, "Simulation not complete")
        if status == "failed":
            raise AOasisWorkerError(500, str(error or "Simulation failed"))
        return dict(result)

    def _complete_simulation(self, simulation_id: str) -> None:
        try:
            with self._lock:
                request = dict(self._runs[simulation_id]["request"])
            result = build_worker_result(request)
            with self._lock:
                self._runs[simulation_id]["status"] = "completed"
                self._runs[simulation_id]["result"] = result
        except Exception as error:  # pragma: no cover - defensive worker guard
            with self._lock:
                self._runs[simulation_id]["status"] = "failed"
                self._runs[simulation_id]["error"] = str(error)


def build_worker_result(request: dict[str, Any]) -> dict[str, Any]:
    simulation_id = _required_string(request, "id")
    platform = _platform(request)
    config = _run_config(request)
    personas = _personas(request)
    seed_text = _seed_text(request)
    private_context = str(request.get("privateContext") or "")
    media_urls = _media_urls(request)
    cost = estimate_run_cost(config)

    events = _build_oasis_events(
        simulation_id=simulation_id,
        platform=platform,
        personas=personas,
        seed_text=seed_text,
        private_context=private_context,
        duration_hours=config.duration_hours,
    )
    visible_events = [
        event for event in events
        if event["action"] in {"create_post", "create_comment", "quote_post"}
        and event.get("text")
    ]
    top_comments = [
        {
            "agentPersonaId": event["agentId"],
            "text": event["text"],
            "sentiment": event["sentiment"],
            "engagements": event["engagementDelta"],
        } for event in visible_events[:8]
    ]
    total_engagements = sum(
        max(0, int(event.get("engagementDelta", 0))) for event in events)
    total_shares = sum(1 for event in events
                       if event["action"] in {"repost", "quote_post"})
    positive = sum(1 for event in events if event["sentiment"] > 0.1)
    negative = sum(1 for event in events if event["sentiment"] < -0.1)
    neutral = max(0, len(events) - positive - negative)
    impressions = max(100, config.active_agents * 35 + total_engagements * 12)

    return {
        "simulationId": simulation_id,
        "status": "completed",
        "propagation": [{
            "impressions": impressions,
            "engagements": total_engagements,
            "shares": total_shares,
            "sentimentDistribution": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
            },
            "reachByHour": _reach_by_hour(config.duration_hours, impressions),
            "topComments": top_comments,
        }],
        "timeline": _timeline(platform, visible_events, total_engagements),
        "network": _network(personas),
        "costUsd": float(cost.usd or 0),
        "completedAt": None,
        "metadata": {
            "runner": "aoasis",
            "variant": AOASIS_VARIANT_NAME,
            "platform": platform,
            "model": config.model,
            "mediaUrls": media_urls,
            "agentContexts": [_agent_context(persona) for persona in personas],
            "oasisEvents": events,
            "costEstimate": asdict(cost),
            "publicSeed": seed_text,
        },
    }


def make_aoasis_worker_server(
    address: tuple[str, int],
    service: AOasisWorkerService,
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                _send_json(self, 200, service.health())
                return
            match = re.fullmatch(r"/api/v1/simulations/([^/]+)/result", path)
            if match:
                _handle(self, lambda: service.get_result(unquote(
                    match.group(1))))
                return
            _send_json(self, 404, {"detail": "Not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/v1/simulations":
                _send_json(self, 404, {"detail": "Not found"})
                return
            _handle(self, lambda: service.start_simulation(_read_json(self)))

    return ThreadingHTTPServer(address, Handler)


def _handle(handler: BaseHTTPRequestHandler, fn: Any) -> None:
    try:
        _send_json(handler, 200, fn())
    except AOasisWorkerError as error:
        _send_json(handler, error.status_code, {"detail": error.detail})
    except json.JSONDecodeError:
        _send_json(handler, 400, {"detail": "Invalid JSON request body"})


def _send_json(
    handler: BaseHTTPRequestHandler,
    status_code: int,
    body: dict[str, Any],
) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length).decode("utf-8")
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        raise AOasisWorkerError(400, "Request body must be a JSON object")
    return data


def _required_string(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise AOasisWorkerError(400, f"{key} is required")
    return item.strip()


def _platform(request: dict[str, Any]) -> str:
    platform = request.get("platform")
    if not isinstance(platform, dict):
        raise AOasisWorkerError(400, "platform is required")
    value = platform.get("platform")
    if not isinstance(value, str):
        raise AOasisWorkerError(400, "platform.platform is required")
    normalized = value.strip().lower()
    if normalized not in {"twitter", "reddit", "instagram"}:
        raise AOasisWorkerError(400, f"Unsupported platform: {value}")
    return normalized


def _run_config(request: dict[str, Any]) -> AOasisRunConfig:
    platform = request.get("platform") if isinstance(request.get("platform"),
                                                     dict) else {}
    run_config = request.get("runConfig") if isinstance(
        request.get("runConfig"), dict) else {}
    return AOasisRunConfig(
        population_id=_required_string(request, "workspaceId"),
        run_id=_required_string(request, "id"),
        platforms=(_platform(request), ),
        active_agents=_int(platform.get("agentCount"), 4),
        background_agents=_int(request.get("backgroundAgentCount"), 0),
        duration_hours=_int(platform.get("durationHours"), 1),
        minutes_per_round=60,
        execution_mode="manual",
        model=str(request.get("modelName") or run_config.get("modelName")
                  or "google/gemini-3.1-flash-lite-preview"),
        public_seed=_seed_text(request),
        private_context=str(request.get("privateContext") or ""),
        asset_context={
            "mediaUrls": _media_urls(request),
        },
    )


def _int(value: Any, fallback: int) -> int:
    return value if isinstance(value, int) and value > 0 else fallback


def _personas(request: dict[str, Any]) -> list[dict[str, Any]]:
    value = request.get("personas")
    if not isinstance(value, list) or not value:
        return [{
            "personaId": "aoasis_skeptic",
            "name": "Skeptical Buyer",
            "archetype": "skeptical buyer",
            "personalityPrompt": "Checks claims and asks for proof.",
            "behaviorTraits": {
                "traits": ["risk-sensitive"],
                "socialGroups": ["value-seeking buyers"],
            },
        }]
    return [item for item in value if isinstance(item, dict)] or _personas({})


def _seed_text(request: dict[str, Any]) -> str:
    seed = request.get("seed")
    if isinstance(seed, dict) and isinstance(seed.get("content"), list):
        for item in seed["content"]:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text = item["text"].strip()
                if text:
                    return text
    return "New product creative under review."


def _media_urls(request: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seed = request.get("seed")
    if isinstance(seed, dict) and isinstance(seed.get("content"), list):
        for item in seed["content"]:
            if isinstance(item, dict) and isinstance(item.get("mediaUrls"),
                                                    list):
                for url in item["mediaUrls"]:
                    if isinstance(url, str) and url and url not in urls:
                        urls.append(url)
    return urls


def _build_oasis_events(
    simulation_id: str,
    platform: str,
    personas: list[dict[str, Any]],
    seed_text: str,
    private_context: str,
    duration_hours: int,
) -> list[dict[str, Any]]:
    events = []
    seed_post_id = f"{simulation_id}:seed"
    for index, persona in enumerate(personas):
        hour = min(duration_hours - 1, round(index * max(duration_hours, 1) /
                                            max(len(personas), 1)))
        agent_id = _persona_id(persona, index)
        text, sentiment = _reaction_text(persona, seed_text, private_context)
        action = "create_comment" if platform in {"reddit", "instagram"} else (
            "quote_post" if index % 2 else "create_post")
        if index == 0:
            action = "create_post"
        events.append({
            "action": action,
            "rawAction": action,
            "agentId": agent_id,
            "userId": agent_id,
            "postId": seed_post_id,
            "text": text,
            "sentiment": sentiment,
            "virtualHour": hour,
            "engagementDelta": _engagement(persona, sentiment, index),
            "metadata": {
                "platform": platform,
                "persona": _agent_context(persona),
            },
        })
        if index % 2 == 1:
            events.append({
                "action": "like_post",
                "rawAction": "like_post",
                "agentId": agent_id,
                "userId": agent_id,
                "postId": seed_post_id,
                "text": "",
                "sentiment": max(0, sentiment),
                "virtualHour": hour,
                "engagementDelta": 1,
                "metadata": {
                    "platform": platform,
                    "persona": _agent_context(persona),
                },
            })
    return events


def _reaction_text(
    persona: dict[str, Any],
    seed_text: str,
    private_context: str,
) -> tuple[str, float]:
    context = _agent_context(persona)
    joined = " ".join([
        str(persona.get("archetype") or ""),
        str(persona.get("personalityPrompt") or ""),
        " ".join(str(item) for item in context.get("traits", [])),
        " ".join(str(item) for item in context.get("trustNeeds", [])),
    ]).lower()
    if any(word in joined for word in ["skeptic", "risk", "price", "warranty"]):
        return (
            "The visual may stop the scroll, but I need material specs, "
            "price context, and warranty proof before I would share or buy.",
            -0.35,
        )
    if any(word in joined for word in ["visual", "aesthetic", "creator"]):
        return (
            "The hook is polished enough to earn a first look. If the landing "
            "page backs up the product story, this can travel quickly.",
            0.42,
        )
    if any(word in joined for word in ["brand", "strategy", "position"]):
        return (
            "The creative creates attention, but category clarity and brand "
            "specificity need to land before the conversation turns into doubt.",
            0.05,
        )
    return (
        "I would compare the promise against real use cases before trusting "
        "the image. Strong presentation helps, but proof carries the purchase.",
        -0.05,
    )


def _engagement(persona: dict[str, Any], sentiment: float, index: int) -> int:
    groups = _agent_context(persona).get("socialGroups", [])
    group_boost = len(groups) if isinstance(groups, list) else 0
    return max(1, 4 + group_boost + index + round(abs(sentiment) * 10))


def _persona_id(persona: dict[str, Any], index: int) -> str:
    value = persona.get("personaId")
    return value if isinstance(value, str) and value else f"aoasis_agent_{index}"


def _agent_context(persona: dict[str, Any]) -> dict[str, Any]:
    traits = persona.get("behaviorTraits")
    if not isinstance(traits, dict):
        traits = {}
    return {
        "personaId": persona.get("personaId"),
        "name": persona.get("name"),
        "archetype": persona.get("archetype"),
        "societyCore": traits.get("societyCore"),
        "traits": list(traits.get("traits") or traits.get("societyTraits")
                       or []),
        "interests": list(traits.get("interests")
                          or traits.get("societyInterests") or []),
        "dislikes": list(traits.get("dislikes")
                         or traits.get("societyDislikes") or []),
        "trustNeeds": list(traits.get("trustNeeds")
                           or traits.get("societyTrustNeeds") or []),
        "socialGroups": list(traits.get("socialGroups") or []),
    }


def _reach_by_hour(duration_hours: int, impressions: int) -> list[dict[str, int]]:
    points = sorted({0, max(0, duration_hours // 2), max(0, duration_hours - 1)})
    return [{
        "hour": hour,
        "cumulativeReach": max(1, round(impressions * ((index + 1) / len(points)))),
    } for index, hour in enumerate(points)]


def _timeline(
    platform: str,
    visible_events: list[dict[str, Any]],
    total_engagements: int,
) -> list[dict[str, Any]]:
    average = (
        sum(float(event["sentiment"]) for event in visible_events) /
        len(visible_events)
    ) if visible_events else 0
    direction = "positive" if average >= 0 else "negative"
    return [
        {
            "type": "sentiment-shift",
            "direction": direction,
            "magnitude": round(min(1, abs(average)), 2),
            "hour": visible_events[0]["virtualHour"] if visible_events else 0,
        },
        {
            "type": "viral-threshold",
            "postId": f"{platform}:seed",
            "engagements": total_engagements,
            "hour": visible_events[-1]["virtualHour"] if visible_events else 1,
        },
    ]


def _network(personas: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [_agent_context(persona) for persona in personas]
    return {
        "nodes": nodes,
        "edges": [
            {
                "source": nodes[index]["personaId"],
                "target": nodes[index + 1]["personaId"],
                "relationship": "observes",
            } for index in range(max(0, len(nodes) - 1))
        ],
        "communities": sorted({
            group for node in nodes
            for group in (node.get("socialGroups")
                          if isinstance(node.get("socialGroups"), list) else [])
        }),
    }
