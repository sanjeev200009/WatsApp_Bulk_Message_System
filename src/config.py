import os
from typing import Optional, List
from pydantic import Field, AnyUrl, HttpUrl
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
    BREVO_LIST_ID: Optional[int] = Field(None, description="Brevo List ID to filter contacts")
    BREVO_PHONE_ATTRIBUTE: str = Field("SMS", description="Attribute containing phone number")
    BREVO_OPT_OUT_ATTRIBUTE: str = Field("OPT_OUT", description="Attribute for opt-out status")

    # Template Configuration
    TEMPLATE_NAME: str = Field(..., description="Name of the approved template")
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
