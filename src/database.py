import requests
import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from .config import settings
from .logger import logger
from .validators import validate_phone

class BrevoClient:
    """
    Client for interacting with Brevo (Sendinblue) API v3.
    Acts as the source of truth for contacts effectively replacing the SQL database.
    Includes SQLite for persistent send history tracking.
    """
    def __init__(self):
        self.api_key = settings.BREVO_API_KEY
        self.base_url = "https://api.brevo.com/v3"
        self.headers = {
            "api-key": self.api_key,
            "accept": "application/json",
            "content-type": "application/json"
        }
        
        # SQLite for send history tracking
        self.db_path = "send_history.db"
        self.conn = None
        self.cursor = None
        self._init_sqlite()
        
    def _init_sqlite(self):
        """Initialize SQLite connection for send history tracking."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            logger.debug(f"SQLite connection established: {self.db_path}")
        except Exception as e:
            print(f"Failed to initialize SQLite: {e}")  # Use print instead of logger to avoid recursion
            self.conn = None
            self.cursor = None
        
    def verify_connection(self) -> bool:
        """Test API connection by fetching account info."""
        try:
            url = f"{self.base_url}/account"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return True
            logger.error(f"Brevo connection failed. Status: {response.status_code}, Body: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Brevo connection error: {e}")
            return False

    def get_eligible_recipients(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch contacts from Brevo that haven't been sent this template before.
        Includes proper SUBSCRIBED consent filtering and pagination.
        
        Args:
            limit: Maximum number of eligible recipients to return
            
        Returns:
            List of dictionaries containing user details normalized to our app structure:
            {'id': str, 'phone': str, 'last_sent_at': None}
        """
        url = f"{self.base_url}/contacts"
        template_name = settings.TEMPLATE_NAME
        normalized_contacts = []
        offset = 0
        page_limit = 100  # Brevo's max per page
        max_pages = 50  # Safety limit to prevent infinite loops
        pages_fetched = 0
        
        # Keep fetching pages until we have enough eligible contacts or exhaust all contacts
        while len(normalized_contacts) < limit and pages_fetched < max_pages:
            params = {
                "limit": page_limit,
                "offset": offset,
                "sort": "desc"
            }
            
            # Add list filtering if specified
            if settings.BREVO_LIST_ID:
                params["listId"] = settings.BREVO_LIST_ID

            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                contacts = data.get('contacts', [])
                
                # If no more contacts, break
                if not contacts:
                    logger.info(f"No more contacts found after {pages_fetched} pages")
                    break
                    
                logger.debug(f"Processing page {pages_fetched + 1}: {len(contacts)} contacts (offset: {offset})")
                
                for contact in contacts:
                    contact_id = contact.get('id')
                    attributes = contact.get('attributes', {})
                    
                    # CRITICAL: Check SUBSCRIBED status first
                    # Brevo tracks subscription status per list
                    if settings.BREVO_LIST_ID:
                        # If filtering by specific list, contact must be subscribed to that list
                        list_ids = contact.get('listIds', [])
                        if settings.BREVO_LIST_ID not in list_ids:
                            logger.debug(f"Skipping contact {contact_id}: Not subscribed to list {settings.BREVO_LIST_ID}")
                            continue
                    else:
                        # If no specific list, check general email subscription status
                        if contact.get('emailBlacklisted', True):  # Default to True for safety
                            logger.debug(f"Skipping contact {contact_id}: Email not subscribed")
                            continue
                    
                    # Check Opt-Out and Blacklisting
                    is_blacklisted = contact.get('emailBlacklisted', False) or contact.get('smsBlacklisted', False)
                    
                    if is_blacklisted:
                        logger.debug(f"Skipping contact {contact_id}: Blacklisted")
                        continue
                        
                    custom_opt_out = attributes.get(settings.BREVO_OPT_OUT_ATTRIBUTE, False)
                    if custom_opt_out:
                        logger.debug(f"Skipping contact {contact_id}: Custom opt-out")
                        continue

                    # Get Phone
                    phone = attributes.get(settings.BREVO_PHONE_ATTRIBUTE)
                    
                    if not phone:
                        # Try to fall back to 'mobile' field if standard attribute fails
                        phone = contact.get('mobile') or contact.get('sms')
                    
                    if not phone:
                        logger.debug(f"Skipping contact {contact_id}: No phone number found in {settings.BREVO_PHONE_ATTRIBUTE}")
                        continue

                    # Normalize and validate phone
                    try:
                        clean_phone = validate_phone(str(phone))
                    except ValueError as e:
                        logger.debug(f"Skipping contact {contact_id}: Invalid phone {phone} - {e}")
                        continue
                    
                    # Skip if already sent this template successfully
                    if self.was_sent_before(clean_phone, template_name):
                        logger.debug(f"Skipping contact {contact_id}: Already sent template '{template_name}'")
                        continue

                    normalized_contacts.append({
                        'id': str(contact_id),
                        'phone': clean_phone,
                        'last_sent_at': None
                    })
                    
                    # Stop when we have enough eligible contacts
                    if len(normalized_contacts) >= limit:
                        break
                
                # Move to next page
                offset += page_limit
                pages_fetched += 1
                
                # If we got fewer contacts than page_limit, we've reached the end
                if len(contacts) < page_limit:
                    logger.info(f"Reached end of contacts after {pages_fetched} pages")
                    break
                    
            except Exception as e:
                logger.error(f"Failed to fetch contacts from Brevo (page {pages_fetched + 1}): {e}")
                raise
        
        logger.info(f"Found {len(normalized_contacts)} eligible recipients after checking {pages_fetched} pages")
        return normalized_contacts[:limit]  # Ensure we don't exceed requested limit

    def update_last_sent(self, user_id: str):
        """
        No-op for Brevo unless we want to update a custom attribute.
        Currently we rely on local logs for 'sent today' checks.
        """
        pass
        
    def create_tables_if_dev(self):
        """Create SQLite tables for send history tracking."""
        if not self.conn:
            logger.warning("SQLite not initialized. Cannot create tables.")
            return
            
        try:
            # Create send_history table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS send_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    sent_at DATETIME NOT NULL,
                    status TEXT NOT NULL, -- 'success' or 'failed'
                    wamid TEXT,
                    error TEXT,
                    UNIQUE(phone, template_name, status) ON CONFLICT REPLACE
                )
            ''')
            
            # Create index for fast lookups
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_phone_template 
                ON send_history(phone, template_name, status)
            ''')
            
            self.conn.commit()
            logger.debug("Send history tables created/verified")
            
        except Exception as e:
            logger.error(f"Failed to create SQLite tables: {e}")
    
    def was_sent_before(self, phone: str, template_name: str) -> bool:
        """Check if phone was already successfully sent this template."""
        if not self.cursor:
            return False
            
        try:
            self.cursor.execute('''
                SELECT 1 FROM send_history 
                WHERE phone = ? AND template_name = ? AND status = 'success'
                LIMIT 1
            ''', (phone, template_name))
            
            return self.cursor.fetchone() is not None
            
        except Exception as e:
            logger.error(f"Error checking send history: {e}")
            return False
    
    def record_send(self, phone: str, template_name: str, status: str, wamid: str = None, error: str = None):
        """Record send attempt in persistent history."""
        if not self.cursor:
            logger.warning("SQLite not available. Cannot record send.")
            return
            
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO send_history 
                (phone, template_name, sent_at, status, wamid, error)
                VALUES (?, ?, datetime('now'), ?, ?, ?)
            ''', (phone, template_name, status, wamid, error))
            
            self.conn.commit()
            logger.debug(f"Recorded {status} send to {phone} for template {template_name}")
            
        except Exception as e:
            logger.error(f"Failed to record send: {e}")

# Global database instance
db = BrevoClient()
