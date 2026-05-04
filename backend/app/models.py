from pydantic import BaseModel, Field


class Source(BaseModel):
    """Citation returned with an answer for a retrieved documentation chunk."""

    title: str
    path: str
    snippet: str
    score: float | None = None


class AskRequest(BaseModel):
    """Request body for asking a question against one documentation version."""

    version: str = Field(min_length=1)
    query: str = Field(min_length=1)
    includeWorkspace: bool = False


class EvidenceItem(BaseModel):
    """One retrieved source item placed on the temporary answer evidence board."""

    id: str
    title: str
    path: str
    snippet: str
    score: float | None = None
    relevanceNote: str


class RetrievalTaskPlan(BaseModel):
    """Per-request plan for using retrieved evidence to synthesize an answer."""

    version: str
    query: str
    intent: str
    steps: list[str]
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


class VersionsResponse(BaseModel):
    """Available documentation versions and the version selected by default."""

    versions: list[str]
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
