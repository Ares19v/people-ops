import os
from typing import List, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App & Organization
    APP_NAME: str = "Google ADK Multi-Agent HR Platform"
    ORGANIZATION_NAME: str = "Intelera Technologies"
    COMPANY_DOMAIN: str = "intelera.com"
    DEFAULT_JURISDICTION: str = "MAHARASHTRA"
    ENVIRONMENT: str = "development"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"
    PORT: int = 38290
    BACKEND_PORT: int = 38290
    
    # Security & JWT
    SECRET_KEY: str = "dev_super_secret_jwt_key_at_least_32_characters_long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://hr_user:hr_password@localhost:5432/hr_db"
    SYNC_DATABASE_URL: str = "postgresql://hr_user:hr_password@localhost:5432/hr_db"
    
    # Pinecone (policy RAG, integrated inference). No key = local keyword fallback.
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_INDEX: str = "people-ops-policies"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    PINECONE_EMBED_MODEL: str = "llama-text-embed-v2"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minio_admin"
    S3_SECRET_KEY: str = "minio_secret_password"
    S3_BUCKET_NAME: str = "hr-documents"
    S3_SECURE: bool = False
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    MOCK_SSO_ENABLED: bool = True
    
    # LLM & Multi-Model Engine (Google ADK & LiteLLM)
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    VERTEX_PROJECT_ID: Optional[str] = None
    VERTEX_LOCATION: str = "us-central1"
    GEMINI_MODEL: str = "gemini-3.8-flash"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "groq/openai/gpt-oss-120b"
    MOCK_LLM_ENABLED: bool = True
    # LiteLLM retries (honouring the provider's retry-after) for rate-limited calls. 0 = fail fast, as in the API;
    # the ADK / evaluation tooling sets this so free-tier limits (e.g. Groq 8k tokens/min) slow a run instead of breaking it.
    LLM_NUM_RETRIES: int = 0
    # Sync SQLAlchemy URL for ADK sessions (e.g. the SYNC_DATABASE_URL). Empty = in-memory sessions
    # (lost on restart, not shared between workers).
    ADK_SESSION_DB_URL: Optional[str] = None
    
    # NeMo Guardrails
    NEMO_GUARDRAILS_CONFIG_DIR: str = "app/guardrails/config"
    
    # Observability (LangSmith & Langfuse)
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "hr-multiagent-platform"
    
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_BASE_URL: Optional[str] = None
    LANGFUSE_WEBHOOK_SECRET: str = "dev_langfuse_webhook_secret_key"
    LANGFUSE_WEBHOOK_TOLERANCE_SECONDS: int = 600  # max age of a signed webhook; 0 disables the check
    PROMPT_WATCH_INTERVAL_SECONDS: float = 30.0  # safety-net poll of Langfuse for prompt changes
    LANGFUSE_ENABLED: bool = True
    LANGFUSE_SAMPLE_RATE: float = 1.0
    LANGFUSE_RELEASE: Optional[str] = None

    # Zoho People API Integration
    ZOHO_CLIENT_ID: Optional[str] = None
    ZOHO_CLIENT_SECRET: Optional[str] = None
    ZOHO_REFRESH_TOKEN: Optional[str] = None
    ZOHO_ACCOUNTS_URL: str = "https://accounts.zoho.in/oauth/v2/token"
    ZOHO_BASE_URL: str = "https://people.zoho.in/people/api"
    ZOHO_ORG_ID: str = "intelera_people_01"
    ZOHO_WEBHOOK_SECRET: Optional[str] = None
    ZOHO_MOCK_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Strictly validates security configurations in production environments."""
        if self.ENVIRONMENT.lower() == "production":
            if "dev_super_secret" in self.SECRET_KEY:
                raise ValueError("CRITICAL SECURITY ERROR: Default dev SECRET_KEY cannot be used in production.")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("CRITICAL SECURITY ERROR: Wildcard CORS '*' with credentials is forbidden in production.")
            if "dev_langfuse_webhook" in self.LANGFUSE_WEBHOOK_SECRET:
                raise ValueError("CRITICAL SECURITY ERROR: Default LANGFUSE_WEBHOOK_SECRET must be rotated in production.")
            if self.MOCK_SSO_ENABLED:
                raise ValueError("CRITICAL SECURITY ERROR: MOCK_SSO_ENABLED must be false in production.")
            default_credentials = {
                "S3_SECRET_KEY": "minio_secret_password",
            }
            for field, default in default_credentials.items():
                if getattr(self, field) == default:
                    raise ValueError(f"CRITICAL SECURITY ERROR: Default {field} must be rotated in production.")
            if ":hr_password@" in self.DATABASE_URL or ":hr_password@" in self.SYNC_DATABASE_URL:
                raise ValueError("CRITICAL SECURITY ERROR: Default database password must be rotated in production.")
        return self

settings = Settings()
