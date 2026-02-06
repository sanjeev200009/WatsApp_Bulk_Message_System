import pytest
from unittest.mock import MagicMock, patch
from src.database import BrevoClient, settings

class TestBrevoClient:
    
    @patch('src.database.requests.get')
    def test_verify_connection_success(self, mock_get):
        mock_get.return_value.status_code = 200
        client = BrevoClient()
        assert client.verify_connection() is True
        mock_get.assert_called_with(
            "https://api.brevo.com/v3/account", 
            headers=client.headers, 
            timeout=10
        )

    @patch('src.database.requests.get')
    def test_verify_connection_failure(self, mock_get):
        mock_get.return_value.status_code = 401
        client = BrevoClient()
        assert client.verify_connection() is False

    @patch('src.database.requests.get')
    def test_get_eligible_recipients(self, mock_get):
        client = BrevoClient()
        
        # Mock Response Data
        mock_response = {
            "contacts": [
                {
                    "id": 1,
                    "attributes": {"SMS": "1234567890", "OPT_OUT": False},
                    "emailBlacklisted": False,
                    "smsBlacklisted": False
                },
                {
                    "id": 2,
                    "attributes": {"SMS": "0987654321", "OPT_OUT": True}, # Custom opt out
                    "emailBlacklisted": False,
                    "smsBlacklisted": False
                },
                {
                    "id": 3,
                    "attributes": {"SMS": "1122334455"},
                    "smsBlacklisted": True # System blacklist
                }
            ]
        }
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response
        
        # We expect only ID 1 to be returned
        # ID 2 is opted out via custom attribute
        # ID 3 is blacklisted by Brevo system
        
        users = client.get_eligible_recipients()
        
        assert len(users) == 1
        assert users[0]['id'] == "1"
        assert users[0]['phone'] == "1234567890"

    @patch('src.database.requests.get')
    def test_get_eligible_recipients_with_list_id(self, mock_get):
        settings.BREVO_LIST_ID = 5
        client = BrevoClient()
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"contacts": []}
        
        client.get_eligible_recipients()
        
        # Assert listId param was passed
        args, kwargs = mock_get.call_args
        assert kwargs['params']['listId'] == 5
