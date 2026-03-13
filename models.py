"""Pydantic models for Learning Tool API."""

from pydantic import BaseModel
from typing import Optional


# ---- Query models ----

class QueryRequest(BaseModel):
    session_id: Optional[str] = None
    parent_node_id: Optional[str] = None
    prompt_text: str
    mode: str = "initial"  # initial | explain | deeper | question
    highlighted_text: Optional[str] = None
    user_question: Optional[str] = None
    provider_id: Optional[str] = None


class QueryResponse(BaseModel):
    job_id: str
    status: str
    engineered_prompt: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # queued | running | complete | error
    elapsed_seconds: float = 0
    response_html: Optional[str] = None
    response_text: Optional[str] = None
    error_message: Optional[str] = None


# ---- Session models ----

class SessionCreate(BaseModel):
    name: str = "Untitled Session"


class SessionRename(BaseModel):
    name: str


class SessionSummary(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    node_count: int = 0


class ViewportState(BaseModel):
    panX: float = 0
    panY: float = 0
    zoom: float = 1.0


class NodeData(BaseModel):
    id: str
    parent_id: Optional[str] = None
    highlight_id: Optional[str] = None
    x: float = 0
    y: float = 0
    width: Optional[float] = None
    height: Optional[float] = None
    prompt_text: str = ""
    prompt_mode: str = "initial"
    prompt_collapsed: Optional[bool] = None
    response_collapsed: Optional[bool] = None
    response_html: str = ""
    response_text: str = ""
    highlighted_text: Optional[str] = None
    status: str = "pending"
    created_at: str = ""


class EdgeData(BaseModel):
    id: str
    source_node_id: str
    source_highlight_id: str
    target_node_id: str


class HighlightData(BaseModel):
    id: str
    node_id: str
    text: str
    color: str = "rgba(59,130,246,0.3)"


class SessionFull(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    viewport: ViewportState = ViewportState()
    nodes: dict[str, NodeData] = {}
    edges: list[EdgeData] = []
    highlights: dict[str, HighlightData] = {}


class SessionSaveRequest(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    viewport: ViewportState = ViewportState()
    nodes: dict[str, NodeData] = {}
    edges: list[EdgeData] = []
    highlights: dict[str, HighlightData] = {}


# ---- Provider models ----

class ProviderCreate(BaseModel):
    alias: str
    type: str = "openai-compatible"  # openai-compatible | claude-cli
    url: str = ""
    model: str = ""
    api_key: str = ""
    enabled: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 300


class ProviderUpdate(BaseModel):
    alias: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    timeout: Optional[int] = None


class DefaultProviderSet(BaseModel):
    provider_id: Optional[str] = None
