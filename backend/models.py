from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    TENANT_USER = "tenant_user"

class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"

class OpportunitySource(str, Enum):
    HIGHERGOV = "highergov"
    PERPLEXITY = "perplexity"
    MANUAL = "manual"

class IntelligenceType(str, Enum):
    COMPETITIVE = "competitive"
    NEWS = "news"
    MARKET = "market"

# Base Models
class MongoModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

# User Models
class UserBase(MongoModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.TENANT_USER
    tenant_id: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(MongoModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None

class User(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

class UserInDB(User):
    hashed_password: str

# Authentication Models
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenData(BaseModel):
    user_id: str
    email: str
    role: UserRole
    tenant_id: Optional[str] = None

# Tenant Models
class BrandingConfig(MongoModel):
    logo_url: Optional[str] = None
    logo_base64: Optional[str] = None  # For uploaded logos
    primary_color: str = "hsl(210, 85%, 52%)"
    secondary_color: str = "hsl(265, 60%, 55%)"
    accent_color: str = "hsl(142, 70%, 45%)"
    text_color: str = "hsl(0, 0%, 98%)"
    # Visual effects and background
    background_image_url: Optional[str] = None
    background_image_base64: Optional[str] = None
    visual_theme: str = "default"  # default, brushed_metal, nvg_green, executive_gloss, tactical_dark, govt_blue, high_tech_sheen
    enable_glow_effects: bool = False
    enable_sheen_overlay: bool = False

class SearchProfile(MongoModel):
    naics_codes: List[str] = []
    keywords: List[str] = []
    interest_areas: List[str] = []
    competitors: List[str] = []
    # HigherGov API configuration
    highergov_api_key: Optional[str] = None  # Per-tenant API key (falls back to default)
    highergov_search_id: Optional[str] = None  # Saved search ID from HigherGov platform
    fetch_full_documents: bool = False
    fetch_nsn: bool = False
    fetch_grants: bool = True
    fetch_contracts: bool = True
    # Auto-update settings
    auto_update_enabled: bool = True
    auto_update_interval_hours: int = 24  # How often to poll HigherGov

class IntelligenceConfig(MongoModel):
    """Configuration for intelligence report generation"""
    enabled: bool = True
    perplexity_prompt_template: Optional[str] = None  # Custom prompt template
    schedule_cron: str = "0 2 * * *"  # Daily at 2 AM UTC by default
    lookback_days: int = 14  # How many days to look back
    deadline_window_days: int = 120  # Future deadline window
    target_sources: List[str] = []  # Specific sites to search
    report_sections: List[str] = [  # Which sections to include
        "executive_summary",
        "top_actions", 
        "opportunities",
        "policy_regulation",
        "defense_signals",
        "sled_by_state",
        "competitor_moves",
        "watchlist",
        "changelog"
    ]
    scoring_weights: Dict[str, int] = {  # For opportunity scoring
        "relevance": 25,
        "amount": 20,
        "timeline": 15,
        "win_probability": 15,
        "strategic_fit": 15,
        "partner_potential": 10
    }

class ScoringWeights(MongoModel):
    value_weight: float = 0.4
    deadline_weight: float = 0.3
    relevance_weight: float = 0.3

class MistralAgentConfig(MongoModel):
    # Option 1: Use pre-created agents from Mistral platform (recommended)
    scoring_agent_id: Optional[str] = None
    opportunities_chat_agent_id: Optional[str] = None
    intelligence_chat_agent_id: Optional[str] = None
    
    # Option 2: Dynamic instructions (fallback if no agent IDs)
    scoring_instructions: Optional[str] = "Analyze this contract opportunity and provide a relevance score and summary."
    opportunities_chat_instructions: Optional[str] = "You are a helpful assistant for contract opportunities."
    intelligence_chat_instructions: Optional[str] = "You are a business intelligence analyst."
    
    # Output schema for AI scoring (JSON schema that agent should follow)
    scoring_output_schema: Optional[Dict[str, Any]] = {
        "relevance_summary": "string",
        "score_adjustment": "number",
        "key_highlights": "array",
        "win_probability": "string",
        "recommended_action": "string"
    }

class ChatPolicy(MongoModel):
    """Tenant chat access policy (super-admin controlled)"""
    enabled: bool = False
    monthly_message_limit: Optional[int] = None  # None = unlimited
    max_user_chars: int = 2000
    max_assistant_tokens: int = 1000
    max_turns_history: int = 10


class ChatUsage(MongoModel):
    """Tracks monthly chat usage for quota enforcement"""
    month: str = ""  # Format: "YYYY-MM"
    messages_used: int = 0


class TenantKnowledge(MongoModel):
    """Tenant knowledge base for Mini-RAG injection into chat"""
    enabled: bool = False
    company_profile: str = ""
    key_facts: List[str] = []
    offerings: List[str] = []
    differentiators: List[str] = []
    prohibited_claims: List[str] = []
    tone_guidelines: str = ""
    updated_at: Optional[str] = None  # ISO string
    max_context_chars: int = 2000
    retrieval_mode: str = "keyword"  # "none" | "keyword"
    max_snippets: int = 5


class KnowledgeSnippet(MongoModel):
    """Individual knowledge snippet for retrieval"""
    id: str
    tenant_id: str
    title: str
    content: str
    tags: List[str] = []
    created_at: str
    updated_at: str


class TenantBase(MongoModel):
    name: str
    slug: str
    is_master_client: bool = False  # Can resell and white-label to their clients
    master_client_id: Optional[str] = None  # If this is a sub-client, references master
    master_branding: Optional[BrandingConfig] = None  # Master's white-label config
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    search_profile: SearchProfile = Field(default_factory=SearchProfile)
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    agent_config: MistralAgentConfig = Field(default_factory=MistralAgentConfig)
    intelligence_config: IntelligenceConfig = Field(default_factory=IntelligenceConfig)
    chat_policy: ChatPolicy = Field(default_factory=ChatPolicy)
    chat_usage: Optional[ChatUsage] = None  # Lazily initialized on first chat
    tenant_knowledge: Optional[TenantKnowledge] = None  # Mini-RAG knowledge base
    status: TenantStatus = TenantStatus.ACTIVE

class TenantCreate(TenantBase):
    pass

class TenantUpdate(MongoModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    branding: Optional[BrandingConfig] = None
    search_profile: Optional[SearchProfile] = None
    scoring_weights: Optional[ScoringWeights] = None
    agent_config: Optional[MistralAgentConfig] = None
    chat_policy: Optional[ChatPolicy] = None
    tenant_knowledge: Optional[TenantKnowledge] = None
    status: Optional[TenantStatus] = None

class Tenant(TenantBase):
    id: str
    created_at: datetime
    updated_at: datetime
    last_synced_at: Optional[datetime] = None
    rate_limit_used: int = 0
    rate_limit_monthly: int = 500
    rate_limit_reset_date: Optional[datetime] = None

# Opportunity Models
class OpportunityBase(MongoModel):
    external_id: str
    title: str
    description: str
    agency: Optional[str] = None
    due_date: Optional[datetime] = None
    estimated_value: Optional[str] = None
    naics_code: Optional[str] = None
    keywords: List[str] = []
    source_type: OpportunitySource = OpportunitySource.MANUAL
    source_url: Optional[str] = None
    raw_data: Dict[str, Any] = {}
    # Client-editable fields
    client_status: Optional[str] = "new"  # new, interested, dismissed, won, lost
    client_notes: Optional[str] = None
    client_tags: List[str] = []
    is_archived: bool = False

class OpportunityCreate(OpportunityBase):
    tenant_id: str

class Opportunity(OpportunityBase):
    id: str
    tenant_id: str
    score: float = 0  # Changed to float to handle decimal scores
    ai_relevance_summary: Optional[str] = None
    captured_date: datetime
    created_at: datetime
    updated_at: datetime

# Intelligence Models
class IntelligenceBase(MongoModel):
    title: str
    summary: str
    content: str
    type: IntelligenceType = IntelligenceType.NEWS
    source_urls: List[str] = []
    keywords: List[str] = []
    metadata: Dict[str, Any] = {}
    # Client-editable fields
    is_archived: bool = False
    client_notes: Optional[str] = None

class IntelligenceCreate(IntelligenceBase):
    tenant_id: str

class Intelligence(IntelligenceBase):
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime

# Chat Models
class ChatMessageBase(MongoModel):
    conversation_id: str
    role: str  # "user" or "assistant"
    content: str
    agent_id: Optional[str] = None

class ChatMessageCreate(ChatMessageBase):
    tenant_id: str
    user_id: str

class ChatMessage(ChatMessageBase):
    id: str
    tenant_id: str
    user_id: str
    created_at: datetime

# Atomic Chat Turn Model (single document for atomicity)
class ChatTurnMessage(MongoModel):
    content: str
    timestamp: str

class ChatTurn(MongoModel):
    id: str
    conversation_id: str
    tenant_id: str
    user_id: str
    user: ChatTurnMessage
    assistant: ChatTurnMessage
    agent_type: str
    created_at: str

# Sync Log Models
class SyncLog(MongoModel):
    id: str
    tenant_id: str
    sync_type: str  # "opportunities" or "intelligence"
    sync_timestamp: datetime
    records_fetched: int = 0
    records_created: int = 0
    records_updated: int = 0
    errors: List[str] = []
    sync_duration_seconds: float = 0.0
    status: str = "success"  # "success" or "failed"

# Response Models
class PaginationMetadata(BaseModel):
    total: int
    page: int
    per_page: int
    pages: int

class PaginatedResponse(BaseModel):
    data: List[Any]
    pagination: PaginationMetadata