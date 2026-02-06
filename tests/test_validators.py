import pytest
from src.validators import validate_phone, mask_phone

class TestValidators:
    def test_validate_phone_valid(self):
        assert validate_phone("15551234567") == "15551234567"
        assert validate_phone("+1-555-123-4567") == "15551234567"
        assert validate_phone("919876543210") == "919876543210"

    def test_validate_phone_invalid(self):
        with pytest.raises(ValueError):
            validate_phone("123")  # Too short
        
        with pytest.raises(ValueError):
            validate_phone("1" * 16) # Too long
            
        with pytest.raises(ValueError):
            validate_phone("") # Empty

    def test_mask_phone(self):
        assert mask_phone("15551234567") == "15...67"
        assert mask_phone("1234") == "12...34"
        assert mask_phone("123") == "****"
        assert mask_phone(None) == "****"
