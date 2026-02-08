import os
import json
from typing import Optional, List, Dict
from pydantic import Field, AnyUrl, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

    # Environment
    ENV: str = Field(..., description="Environment: test or prod")

    # WhatsApp API Configuration
    PHONE_NUMBER_ID: str = Field(..., description="WhatsApp Phone Number ID")
    WHATSAPP_TOKEN: str = Field(..., description="WhatsApp System User Access Token")
    WA_BUSINESS_ACCOUNT_ID: Optional[str] = Field(None, description="WhatsApp Business Account ID")
    WA_API_VERSION: str = Field("v21.0", description="WhatsApp Cloud API Version")

    # Brevo Configuration
    BREVO_API_KEY: str = Field(..., description="Brevo API Key (xkeysib-...)")
    BREVO_LIST_ID: Optional[int] = Field(None, description="Brevo List ID to filter contacts (deprecated - use EXPERIENCE_LIST_MAP)")
    BREVO_PHONE_ATTRIBUTE: str = Field("SMS", description="Attribute containing phone number")
    BREVO_OPT_OUT_ATTRIBUTE: str = Field("OPT_OUT", description="Attribute for opt-out status")

    # Experience Targeting (Job Campaigns)
    EXPERIENCE_LIST_MAP: Optional[str] = Field(None, description='JSON mapping of experience levels to list IDs: {"junior":123, "mid":456, "senior":789}')
    JOB_CAMPAIGN_ID: Optional[str] = Field(None, description="Unique campaign ID for this job (required in prod)")
    
    # Template Configuration
    TEMPLATE_NAME: str = Field(..., description="Name of the approved template (default/fallback)")
    TEMPLATE_NAME_JUNIOR: Optional[str] = Field(None, description="Template name for junior level (falls back to TEMPLATE_NAME)")
    TEMPLATE_NAME_MID: Optional[str] = Field(None, description="Template name for mid level (falls back to TEMPLATE_NAME)")
    TEMPLATE_NAME_SENIOR: Optional[str] = Field(None, description="Template name for senior level (falls back to TEMPLATE_NAME)")
    TEMPLATE_NAME_EXECUTIVE: Optional[str] = Field(None, description="Template name for executive level (falls back to TEMPLATE_NAME)")
    LANGUAGE_CODE: str = Field("en", description="Language code of the template")
    IMAGE_URL: HttpUrl = Field(..., description="URL of the image for template header")

    # Rate Limiting & Control
    DAILY_LIMIT: int = Field(100, description="Maximum number of messages to send per day")
    SEND_DELAY_SECONDS: float = Field(5.0, description="Minimum seconds to wait between calls")
    MAX_RETRIES: int = Field(2, description="Maximum retry attempts per message")
    RETRY_BACKOFF_SECONDS: float = Field(5.0, description="Base seconds for exponential backoff")

    # Logging
    LOG_LEVEL: str = Field("INFO", description="Logging level")
    LOG_FILE: str = Field("logs/whatsapp_marketing.log", description="Path to application log file")
    RESULT_LOG_FILE: str = Field("logs/send_results.jsonl", description="Path to JSONL result log")

    @property
    def api_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.WA_API_VERSION}"
    
    @property
    def is_test_env(self) -> bool:
        return self.ENV.lower() == "test"
    
    @property
    def is_prod_env(self) -> bool:
        return self.ENV.lower() == "prod"
    
    def get_experience_list_map(self) -> Dict[str, int]:
        """Parse EXPERIENCE_LIST_MAP JSON and return as dict."""
        if not self.EXPERIENCE_LIST_MAP:
            return {}
        try:
            mapping = json.loads(self.EXPERIENCE_LIST_MAP)
            # Validate all values are integers
            return {k.lower(): int(v) for k, v in mapping.items()}
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid EXPERIENCE_LIST_MAP format: {e}. Expected JSON like {{'junior':123, 'mid':456, 'senior':789}}")
    
    def get_template_name_for_level(self, level: str) -> str:
        """Get the template name for a list by searching for level keywords in its name."""
        if not level:
            return self.TEMPLATE_NAME
            
        name = level.lower()
        
        if ("junior" in name or "intern" in name or "entry" in name) and self.TEMPLATE_NAME_JUNIOR:
            return self.TEMPLATE_NAME_JUNIOR
        elif ("senior" in name) and self.TEMPLATE_NAME_SENIOR:
            return self.TEMPLATE_NAME_SENIOR
        elif ("executive" in name or "director" in name) and self.TEMPLATE_NAME_EXECUTIVE:
            return self.TEMPLATE_NAME_EXECUTIVE
        elif ("mid" in name or "associate" in name) and self.TEMPLATE_NAME_MID:
            return self.TEMPLATE_NAME_MID
            
        return self.TEMPLATE_NAME
    
    def validate_required_fields(self) -> List[str]:
        """Validate all required environment variables are set properly."""
        missing = []
        
        # Check for default/placeholder values
        if "input_your_token_here" in getattr(self, 'WHATSAPP_TOKEN', ''):
            missing.append("WHATSAPP_TOKEN (contains placeholder)")
        if "xkeysib-your-dummy-key-here" in getattr(self, 'BREVO_API_KEY', ''):
            missing.append("BREVO_API_KEY (contains placeholder)")
        
        # Check empty required fields
        required_fields = ['ENV', 'PHONE_NUMBER_ID', 'WHATSAPP_TOKEN', 'BREVO_API_KEY', 'TEMPLATE_NAME']
        for field in required_fields:
            value = getattr(self, field, None)
            if not value or (isinstance(value, str) and not value.strip()):
                missing.append(f"{field} (empty or missing)")
        
        # Check ENV value
        if hasattr(self, 'ENV') and self.ENV.lower() not in ['test', 'prod']:
            missing.append("ENV (must be 'test' or 'prod')")
        
        # Validate EXPERIENCE_LIST_MAP if provided
        if self.EXPERIENCE_LIST_MAP:
            try:
                self.get_experience_list_map()
            except ValueError as e:
                missing.append(f"EXPERIENCE_LIST_MAP: {str(e)}")
        
        # In production, JOB_CAMPAIGN_ID is required for job campaigns
        if self.is_prod_env and self.EXPERIENCE_LIST_MAP and not self.JOB_CAMPAIGN_ID:
            missing.append("JOB_CAMPAIGN_ID (required in production for job campaigns)")
        
        return missing

# Global settings instance
try:
    settings = Settings()
except Exception as e:
    # We'll allow import without valid settings for tests that mock them,
    # but actual usage will fail if env vars aren't set
    if os.environ.get("PYTEST_CURRENT_TEST"):
        # Create a dummy instance just for import-time safety during tests
        # The tests should mock the actual object
        class DummySettings:
            def __getattr__(self, name):
                return None
        settings = DummySettings()
    else:
        raise
