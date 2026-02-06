import requests
import time
from typing import Dict, Any, Optional
from requests.exceptions import RequestException
from .config import settings
from .logger import logger

class WhatsAppClient:
    """
    Client for interacting with the WhatsApp Cloud API.
    """
    def __init__(self):
        self.base_url = settings.api_base_url
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def send_template_message(self, 
                              to_phone: str, 
                              template_name: str = None, 
                              language_code: str = None,
                              image_url: str = None) -> tuple[Dict[str, Any], int]:
        """
        Send a template message to a specific phone number.
        
        Args:
            to_phone: Recipient phone number (E.164 format without +)
            template_name: Name of the template (defaults to config)
            language_code: Language of the template (defaults to config)
            image_url: URL for the image header (defaults to config)
            
        Returns:
            Tuple of (API response dictionary, HTTP status code)
        """
        template_name = template_name or settings.TEMPLATE_NAME
        language_code = language_code or settings.LANGUAGE_CODE
        image_url = image_url or str(settings.IMAGE_URL)

        url = f"{self.base_url}/{settings.PHONE_NUMBER_ID}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                },
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "image",
                                "image": {
                                    "link": image_url
                                }
                            }
                        ]
                    }
                ]
            }
        }

        retry_count = 0
        last_error = None

        while retry_count <= settings.MAX_RETRIES:
            try:
                if retry_count > 0:
                    sleep_time = settings.RETRY_BACKOFF_SECONDS * (2 ** (retry_count - 1))
                    logger.info(f"Retrying send to {to_phone} (Attempt {retry_count + 1}). Waiting {sleep_time}s...")
                    time.sleep(sleep_time)

                response = requests.post(url, headers=self.headers, json=payload, timeout=30)
                
                # Check for HTTP errors
                response.raise_for_status()
                
                return response.json(), response.status_code
                
            except RequestException as e:
                last_error = e
                # Don't retry on 4xx errors (client errors) except 429 (rate limit)
                status_code = getattr(e.response, 'status_code', 0) if e.response else 0
                
                if 400 <= status_code < 500 and status_code != 429:
                    logger.error(f"Client error sending to {to_phone}: {str(e)} - Response: {e.response.text}")
                    raise e
                    
                logger.warning(f"Error sending to {to_phone}: {str(e)}")
                retry_count += 1
        
        logger.error(f"Failed to send to {to_phone} after {settings.MAX_RETRIES} retries")
        raise last_error
    
    def verify_connection(self) -> bool:
        """Verify WhatsApp API token and phone number ID are valid."""
        try:
            # Test by fetching phone number info
            url = f"{self.base_url}/{settings.PHONE_NUMBER_ID}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                logger.debug("WhatsApp API connection verified")
                return True
            else:
                logger.error(f"WhatsApp API verification failed. Status: {response.status_code}, Body: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"WhatsApp API verification error: {e}")
            return False

# Global client instance
wa_client = WhatsAppClient()
