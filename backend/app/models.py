from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    """Citation returned with an answer for a retrieved documentation chunk."""

    title: str
    path: str
    snippet: str
    score: float | None = None


class GenerationOptions(BaseModel):
    """Per-request generation and retrieval controls selected by the user."""

    model_config = ConfigDict(populate_by_name=True)

    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, alias="topP", ge=0, le=1)
    max_tokens: int | None = Field(default=None, alias="maxTokens", ge=1, le=32768)
    frequency_penalty: float | None = Field(default=None, alias="frequencyPenalty", ge=-2, le=2)
    presence_penalty: float | None = Field(default=None, alias="presencePenalty", ge=-2, le=2)
    reasoning_effort: str | None = Field(default=None, alias="reasoningEffort", pattern="^(none|minimal|low|medium|high|xhigh)$")
    context_window: int | None = Field(default=None, alias="contextWindow", ge=512, le=262144)
    top_k_results: int | None = Field(default=None, alias="topKResults", ge=1, le=20)


class AskRequest(BaseModel):
    """Request body for asking a question against one documentation version."""

    version: str = Field(min_length=1)
    query: str = Field(min_length=1)
    chatProvider: str | None = None
    includeWorkspace: bool = False
    options: GenerationOptions | None = None


class EvidenceItem(BaseModel):
    """One retrieved source item placed on the temporary answer evidence board."""

    id: str
    title: str
    path: str
    snippet: str
    score: float | None = None
    relevanceNote: str


class QueryStep(BaseModel):
    """One visible retrieval and synthesis step for a user question."""

    id: str
    title: str
    description: str
    retrievalQuery: str
    status: str = "pending"
    evidence: list[EvidenceItem] = Field(default_factory=list)
    result: str = ""
    gaps: list[str] = Field(default_factory=list)


class RetrievalTaskPlan(BaseModel):
    """Per-request plan for using retrieved evidence to synthesize an answer."""

    version: str
    query: str
    intent: str
    plannerMode: str = "deterministic"
    steps: list[QueryStep]
    evidence: list[EvidenceItem]
    gaps: list[str] = Field(default_factory=list)


class AnswerWorkspace(BaseModel):
    """Temporary structured workspace used while answering a single request."""

    task: RetrievalTaskPlan


class AskResponse(BaseModel):
    """Answer payload returned by the question endpoint."""

    answer: str
    sources: list[Source]
    workspace: AnswerWorkspace | None = None


class HistoryItem(BaseModel):
    """Saved question, answer, and evidence returned by the history API."""

    id: str
    createdAt: str
    version: str
    question: str
    answer: str
    sources: list[Source]
    workspace: AnswerWorkspace | None = None


class HistoryResponse(BaseModel):
    """Saved query history, newest item first."""

    history: list[HistoryItem]


class VersionsResponse(BaseModel):
    """Available documentation versions and the version selected by default."""

    versions: list[str]
    default: str


class ChatProvidersResponse(BaseModel):
    """Available answer-generation providers and the configured default."""

    providers: list[str]
    default: str


class IngestRequest(BaseModel):
    """Request body for rebuilding a documentation version index."""

    version: str = Field(min_length=1)


class IngestResponse(BaseModel):
    """Summary returned after an ingest run finishes."""

    version: str
    documents: int
    chunks: int
    indexPath: str


class Document(BaseModel):
    """Normalized source document loaded from disk before chunking."""

    text: str
    title: str
    source_path: str


class DocumentChunk(BaseModel):
    """Indexable text segment with metadata used for citations and filtering."""

    text: str
    metadata: dict


class RetrievedChunk(BaseModel):
    """Chunk returned from vector search with display-ready citation fields."""

    text: str
    title: str
    path: str
    score: float | None = None
