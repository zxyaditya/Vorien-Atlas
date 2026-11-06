"""
Atlas Research Workspace API — Projects, Notes, Knowledge Archive
================================================================
Phase 1 endpoints for the Atlasnew frontend.
Mounted at /api via server.py.

Auth: Uses the same ATLAS_ACCESS_CODES env var as the main server middleware.
      The main middleware already validates tokens — these endpoints just need
      to trust that the middleware passed the request through.

Collections (MongoDB):
  - atlas_projects   — research project documents
  - atlas_notes      — research notes per project
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional, List
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

log = logging.getLogger("atlas.workspace")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str_id(doc: dict) -> dict:
    """Convert MongoDB ObjectId fields to str for JSON serialization."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def _oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(400, f"Invalid id: {s!r}")


# ─── Pydantic models ──────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "Active"
    tags: Optional[List[str]] = []
    focus_note: Optional[str] = None

class ProjectPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    focus_note: Optional[str] = None
    scratchpad: Optional[str] = None
    open_questions: Optional[List[str]] = None

class NoteCreate(BaseModel):
    type: str
    title: str
    body: Optional[str] = ""
    resolution_status: Optional[str] = "Open"
    resolution_note: Optional[str] = None
    linked_resources: Optional[List[dict]] = []
    tags: Optional[List[str]] = []
    feature_ids: Optional[List[str]] = []

class NotePatch(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    resolution_status: Optional[str] = None
    resolution_note: Optional[str] = None
    linked_resources: Optional[List[dict]] = None
    tags: Optional[List[str]] = None

class InviteRequest(BaseModel):
    email: str
    role: str

class AISuggestRequest(BaseModel):
    query: str

NOTE_TYPES = {"Hypothesis", "Observation", "Decision", "Finding",
              "Question", "Lesson", "Reference"}


# ─── Router factory ───────────────────────────────────────────────────────────

def build_workspace_router(db) -> APIRouter:
    router = APIRouter(tags=["workspace"])

    projects = db["atlas_projects"]
    notes    = db["atlas_notes"]

    # ═══════════════════════════════════════════════════════════════════════
    # Projects CRUD
    # ═══════════════════════════════════════════════════════════════════════

    @router.get("/projects")
    async def list_projects(
        status: Optional[str] = None,
        sort:   Optional[str] = "updated_at",
        limit:  int = 100,
    ):
        query: dict = {}
        if status:
            query["status"] = status
        cursor = projects.find(query).sort(sort or "updated_at", -1).limit(limit)
        docs = []
        async for doc in cursor:
            pid = str(doc["_id"])
            doc["note_count"] = await notes.count_documents({"project_id": pid})
            doc["dataset_count"] = await db["atlas_datasets"].count_documents({"project_id": pid})
            doc["experiment_count"] = await db["learning_experiments"].count_documents({"spec.tags": pid})
            doc["backtest_count"] = await db["learning_backtests"].count_documents({"spec.tags": pid})
            docs.append(_str_id(doc))
        return docs

    @router.post("/projects", status_code=201)
    async def create_project(body: ProjectCreate):
        now = _now()
        doc = {
            "name":           body.name,
            "description":    body.description or "",
            "status":         body.status or "Active",
            "tags":           body.tags or [],
            "focus_note":     body.focus_note,
            "scratchpad":     "",
            "open_questions": [],
            "experiment_count": 0,
            "dataset_count":    0,
            "backtest_count":   0,
            "note_count":       0,
            "created_at":     now,
            "updated_at":     now,
        }
        result = await projects.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        log.info("Created project %s — %s", doc["_id"], doc["name"])
        return doc

    @router.get("/projects/{project_id}")
    async def get_project(project_id: str):
        doc = await projects.find_one({"_id": _oid(project_id)})
        if not doc:
            raise HTTPException(404, f"Project '{project_id}' not found")
        doc["note_count"] = await notes.count_documents({"project_id": project_id})
        doc["dataset_count"] = await db["atlas_datasets"].count_documents({"project_id": project_id})
        doc["experiment_count"] = await db["learning_experiments"].count_documents({"spec.tags": project_id})
        doc["backtest_count"] = await db["learning_backtests"].count_documents({"spec.tags": project_id})
        return _str_id(doc)

    @router.patch("/projects/{project_id}")
    async def update_project(project_id: str, body: ProjectPatch):
        update = {k: v for k, v in body.dict().items() if v is not None}
        update["updated_at"] = _now()
        result = await projects.update_one({"_id": _oid(project_id)}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(404, "Project not found")
        doc = await projects.find_one({"_id": _oid(project_id)})
        return _str_id(doc)

    @router.delete("/projects/{project_id}")
    async def archive_project(project_id: str):
        """Soft delete — sets status=Archived."""
        result = await projects.update_one(
            {"_id": _oid(project_id)},
            {"$set": {"status": "Archived", "updated_at": _now()}},
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Project not found")
        return {"archived": True}

    # ═══════════════════════════════════════════════════════════════════════
    # Notes per project
    # ═══════════════════════════════════════════════════════════════════════

    @router.get("/projects/{project_id}/notes")
    async def list_notes(
        project_id: str,
        note_type:  Optional[str] = None,
        status:     Optional[str] = None,
    ):
        query: dict = {"project_id": project_id}
        if note_type: query["type"] = note_type
        if status:    query["resolution_status"] = status
        docs = []
        async for doc in notes.find(query).sort("created_at", -1):
            docs.append(_str_id(doc))
        return docs

    @router.post("/projects/{project_id}/notes", status_code=201)
    async def create_note(project_id: str, body: NoteCreate):
        proj = await projects.find_one({"_id": _oid(project_id)})
        if not proj:
            raise HTTPException(404, "Project not found")
        if body.type not in NOTE_TYPES:
            raise HTTPException(400, f"Invalid note type. Choose from: {sorted(NOTE_TYPES)}")
        now = _now()
        doc = {
            "project_id":        project_id,
            "project_name":      proj.get("name", ""),
            "type":              body.type,
            "title":             body.title,
            "body":              body.body or "",
            "resolution_status": body.resolution_status or "Open",
            "resolution_note":   body.resolution_note,
            "linked_resources":  body.linked_resources or [],
            "tags":              body.tags or [],
            "feature_ids":       body.feature_ids or [],
            "created_at":        now,
            "updated_at":        now,
        }
        result = await notes.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        await projects.update_one(
            {"_id": _oid(project_id)},
            {"$inc": {"note_count": 1}, "$set": {"updated_at": now}},
        )
        return doc

    @router.patch("/projects/{project_id}/notes/{note_id}")
    async def update_note(project_id: str, note_id: str, body: NotePatch):
        update = {k: v for k, v in body.dict().items() if v is not None}
        update["updated_at"] = _now()
        result = await notes.update_one(
            {"_id": _oid(note_id), "project_id": project_id},
            {"$set": update},
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Note not found")
        doc = await notes.find_one({"_id": _oid(note_id)})
        return _str_id(doc)

    @router.delete("/projects/{project_id}/notes/{note_id}")
    async def delete_note(project_id: str, note_id: str):
        result = await notes.delete_one({"_id": _oid(note_id), "project_id": project_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Note not found")
        await projects.update_one(
            {"_id": _oid(project_id)},
            {"$inc": {"note_count": -1}, "$set": {"updated_at": _now()}},
        )
        return {"deleted": True}

    # ═══════════════════════════════════════════════════════════════════════
    # Knowledge Archive — cross-project notes search
    # ═══════════════════════════════════════════════════════════════════════

    @router.get("/knowledge/notes")
    async def knowledge_notes(
        q:         Optional[str] = None,
        note_type: Optional[str] = None,
        status:    Optional[str] = None,
        limit:     int = 200,
    ):
        query: dict = {}
        if note_type: query["type"] = note_type
        if status:    query["resolution_status"] = status
        if q:
            query["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"body":  {"$regex": q, "$options": "i"}},
            ]
        docs = []
        async for doc in notes.find(query).sort("created_at", -1).limit(limit):
            docs.append(_str_id(doc))
        return docs

    # ═══════════════════════════════════════════════════════════════════════
    # Workspace & Team (Phase 5)
    # ═══════════════════════════════════════════════════════════════════════

    @router.get("/workspace/team")
    async def list_team_members():
        """Returns team members from atlas_users collection.
        User management is not yet implemented — returns placeholder instructing setup."""
        docs = []
        async for doc in db["atlas_users"].find({}).limit(20):
            doc["_id"] = str(doc["_id"])
            docs.append(doc)
        if not docs:
            return [{"id": "owner", "name": "You (Owner)", "email": "",
                     "role": "Owner", "status": "Active", "last_active": _now()}]
        return docs

    @router.post("/workspace/team/invite")
    async def invite_team_member(req: InviteRequest):
        """Stores an invitation record in atlas_users."""
        now = _now()
        doc = {"email": req.email, "role": req.role,
               "status": "Pending", "last_active": None, "created_at": now}
        result = await db["atlas_users"].insert_one(doc)
        return {"status": "sent", "email": req.email, "role": req.role,
                "id": str(result.inserted_id)}

    # ═══════════════════════════════════════════════════════════════════════
    # Collaborative Presence (Phase 5)
    # ═══════════════════════════════════════════════════════════════════════

    class ConnectionManager:
        def __init__(self):
            self.active_connections: List[WebSocket] = []

        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket):
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

        async def broadcast(self, message: dict):
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except:
                    pass

    manager = ConnectionManager()

    @router.websocket("/workspace/notes/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        await manager.connect(websocket)
        try:
            # Broadcast that this client joined
            await manager.broadcast({"event": "presence", "client_id": client_id, "status": "online"})
            while True:
                data = await websocket.receive_text()
                # Simple echo/broadcast for demonstration
                await manager.broadcast({"event": "message", "client_id": client_id, "data": data})
        except WebSocketDisconnect:
            manager.disconnect(websocket)
            await manager.broadcast({"event": "presence", "client_id": client_id, "status": "offline"})

    # ═══════════════════════════════════════════════════════════════════════
    # AI Assistant (Phase 5)
    # ═══════════════════════════════════════════════════════════════════════

    @router.post("/ai/suggest-features")
    async def ai_suggest_features(req: AISuggestRequest):
        """Real feature registry search: finds features whose name or definition
        matches the query keywords."""
        from atlas_core.compute import list_features
        all_feats = list_features()
        keywords = [w for w in req.query.lower().split() if len(w) > 2]
        if not keywords:
            return {"query": req.query, "suggestions": []}

        def _score(f):
            text = (f.name + " " + (f.definition or "") + " " + (f.family or "")).lower()
            return sum(kw in text for kw in keywords)

        matches = [f for f in all_feats if _score(f) > 0]
        matches.sort(key=_score, reverse=True)
        return {
            "query": req.query,
            "suggestions": [
                {
                    "id": f.id,
                    "name": f.name,
                    "desc": f.definition or "",
                    "family": f.family or "",
                    "layer": f.layer,
                    "relevance": round(_score(f) / max(len(keywords), 1), 2),
                }
                for f in matches[:10]
            ]
        }

    @router.post("/ai/summarize-project/{project_id}")
    async def ai_summarize_project(project_id: str):
        """Generates a structured summary by aggregating real project data:
        experiments, backtests, notes, and datasets from MongoDB."""
        proj = await projects.find_one({"_id": _oid(project_id)})
        if not proj:
            raise HTTPException(404, "Project not found")

        # Gather real data
        n_notes = await notes.count_documents({"project_id": project_id})
        open_qs = await notes.count_documents({"project_id": project_id, "type": "Question", "resolution_status": "Open"})
        hypotheses = await notes.count_documents({"project_id": project_id, "type": "Hypothesis"})
        findings = await notes.count_documents({"project_id": project_id, "type": "Finding"})

        exps = await db["atlas_experiments"].find(
            {"tags": project_id}, {"spec.name": 1, "aggregate": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(5)

        bts = await db["atlas_backtests"].find(
            {"tags": project_id}, {"metrics": 1, "spec.symbol": 1, "created_at": 1}
        ).sort("created_at", -1).to_list(3)

        # Build summary from real data
        lines = [f"# Research Summary: {proj.get('name', 'Project')}\n"]
        lines.append(f"**Status:** {proj.get('status', 'Active')}  ")
        lines.append(f"**Notes:** {n_notes} total ({open_qs} open questions, {hypotheses} hypotheses, {findings} findings)\n")

        if exps:
            lines.append("## Experiments")
            for e in exps:
                acc = e.get("aggregate", {}).get("accuracy_mean", None)
                acc_str = f"{acc:.3f}" if acc else "—"
                lines.append(f"- **{e.get('spec', {}).get('name', 'Unnamed')}** — accuracy: {acc_str}")

        if bts:
            lines.append("\n## Backtests")
            for b in bts:
                m = b.get("metrics", {})
                sharpe = m.get("sharpe_ratio", None)
                sr_str = f"{sharpe:.2f}" if sharpe else "—"
                lines.append(f"- **{b.get('spec', {}).get('symbol', '?')}** — Sharpe: {sr_str}")

        if proj.get("scratchpad"):
            lines.append(f"\n## Scratchpad Excerpt")
            lines.append(proj["scratchpad"][:500] + ("..." if len(proj.get("scratchpad", "")) > 500 else ""))

        lines.append("\n*This summary was auto-generated from your project data. Edit as needed.*")
        return {"summary": "\n".join(lines)}

    return router
