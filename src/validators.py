import re

def validate_phone(phone: str) -> str:
    """
    Validate and format a phone number for WhatsApp API (E.164).
    Removes non-digit characters.
    Must start with country code (no +).
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Cleaned phone number string
        
    Raises:
        ValueError: If phone number is invalid
    """
    if not phone:
        raise ValueError("Phone number is empty")
        
    # Remove all non-digit characters
    cleaned = re.sub(r'\D', '', str(phone))
    
    # Basic length validation (international numbers are usually 10-15 digits)
    if len(cleaned) < 10 or len(cleaned) > 15:
        raise ValueError(f"Phone number length {len(cleaned)} is invalid (expected 10-15 digits)")
        
    return cleaned

def mask_phone(phone: str) -> str:
    """
    Mask a phone number for privacy/logging.
    Shows only the first 2 and last 2 digits.
    
    Args:
        phone: Phone number string
        
    Returns:
        Masked string, e.g. "12...89"
    """
    if not phone or len(phone) < 4:
        return "****"
        
    return f"{phone[:2]}...{phone[-2:]}"
