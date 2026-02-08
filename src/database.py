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

    def get_eligible_recipients(self, limit: int = 50, list_id: int = None, 
                               campaign_key: str = None, experience_level: str = None) -> List[Dict[str, Any]]:
        """
        Fetch contacts from Brevo that haven't been sent this campaign before.
        Supports list-based targeting for job campaigns.
        
        Args:
            limit: Maximum number of eligible recipients to return
            list_id: Brevo list ID to filter contacts (for experience-level targeting)
            campaign_key: Unique campaign identifier (e.g., "2026-02-07-job-003:template_senior")
            experience_level: Experience level label (e.g., "junior", "mid", "senior")
            
        Returns:
            List of dictionaries containing user details normalized to our app structure:
            {'id': str, 'phone': str, 'experience_level': str, 'list_id': int, 'last_sent_at': None}
        """
        url = f"{self.base_url}/contacts"
        
        # Use campaign_key for deduplication, fallback to template_name for backwards compatibility
        dedup_key = campaign_key if campaign_key else settings.TEMPLATE_NAME
        
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
            
            # Prioritize list_id parameter (for job campaigns), fallback to global BREVO_LIST_ID
            target_list_id = list_id if list_id is not None else settings.BREVO_LIST_ID
            if target_list_id:
                params["listIds"] = [target_list_id]

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
                    
                    # CRITICAL: Check list membership (consent gate for this project)
                    if target_list_id:
                        list_ids = contact.get('listIds', [])
                        if target_list_id not in list_ids:
                            logger.debug(f"Skipping contact {contact_id}: Not in target list {target_list_id}")
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
                        # Try fallback fields
                        phone = attributes.get('WHATSAPP') or contact.get('mobile') or contact.get('sms')
                    
                    if not phone:
                        logger.debug(f"Skipping contact {contact_id}: No phone number found in {settings.BREVO_PHONE_ATTRIBUTE}")
                        continue

                    # Normalize and validate phone
                    try:
                        clean_phone = validate_phone(str(phone))
                    except ValueError as e:
                        logger.debug(f"Skipping contact {contact_id}: Invalid phone {phone} - {e}")
                        continue
                    
                    # Skip if already sent this campaign successfully
                    if self.was_sent_before(clean_phone, dedup_key):
                        logger.debug(f"Skipping contact {contact_id}: Already sent campaign '{dedup_key}'")
                        continue

                    normalized_contacts.append({
                        'id': str(contact_id),
                        'phone': clean_phone,
                        'experience_level': experience_level,
                        'list_id': target_list_id,
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

    def get_all_folders(self) -> List[Dict[str, Any]]:
        """
        Fetch all contact folders from Brevo.
        """
        folders = []
        offset = 0
        limit = 50
        try:
            while True:
                url = f"{self.base_url}/contacts/folders?limit={limit}&offset={offset}"
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                batch = response.json().get('folders', [])
                
                # Fetch list count for each folder
                for folder in batch:
                    folder_id = folder['id']
                    # Use a lightweight check or the lists endpoint
                    list_url = f"{self.base_url}/contacts/folders/{folder_id}/lists?limit=1"
                    try:
                        list_res = requests.get(list_url, headers=self.headers, timeout=5)
                        folder['list_count'] = list_res.json().get('count', 0)
                    except:
                        folder['list_count'] = 0

                folders.extend(batch)
                if len(batch) < limit:
                    break
                offset += limit
            return folders
        except Exception as e:
            logger.error(f"Error fetching folders from Brevo: {e}")
            return []

    def get_lists_by_folder_name(self, folder_identifier: str) -> Dict[str, int]:
        """
        Find a folder by name or ID and return its list mapping.
        """
        try:
            # 1. Get all folders using pagination
            folders = []
            offset = 0
            limit = 50
            while True:
                folders_url = f"{self.base_url}/contacts/folders?limit={limit}&offset={offset}"
                response = requests.get(folders_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                batch = response.json().get('folders', [])
                folders.extend(batch)
                if len(batch) < limit:
                    break
                offset += limit
            
            # 2. Find target folder (by ID or Name)
            target_folder = None
            
            # Check if identifier is string and numeric (Folder ID)
            if isinstance(folder_identifier, str) and folder_identifier.isdigit():
                target_id = int(folder_identifier)
                target_folder = next((f for f in folders if f['id'] == target_id), None)
            
            # Fallback/alternative: Check by Name
            if not target_folder:
                target_folder = next((f for f in folders if f['name'].upper() == folder_identifier.upper()), None)
            
            if not target_folder:
                logger.error(f"Folder identifier '{folder_identifier}' not found in Brevo.")
                return {}
            
            # 3. Get all lists DIRECTLY from this folder ID (more reliable and handles many lists)
            folder_id = target_folder['id']
            folder_lists = []
            offset = 0
            limit = 50
            try:
                while True:
                    lists_url = f"{self.base_url}/contacts/folders/{folder_id}/lists?limit={limit}&offset={offset}"
                    response = requests.get(lists_url, headers=self.headers, timeout=10)
                    response.raise_for_status()
                    batch = response.json().get('lists', [])
                    folder_lists.extend(batch)
                    if len(batch) < limit:
                        break
                    offset += limit
            except Exception as list_err:
                logger.warning(f"Direct folder list fetch failed, falling back to account-wide search: {list_err}")
                # Fallback: fetch all and filter (legacy behavior)
                all_lists = []
                offset = 0
                while True:
                    url = f"{self.base_url}/contacts/lists?limit={limit}&offset={offset}"
                    res = requests.get(url, headers=self.headers, timeout=15)
                    res.raise_for_status()
                    batch = res.json().get('lists', [])
                    all_lists.extend(batch)
                    if len(batch) < limit: break
                    offset += limit
                folder_lists = [l for l in all_lists if l.get('folderId') == folder_id]
            
            # 4. Return all lists belonging to this folder with their original names
            mapping = {l['name']: l['id'] for l in folder_lists}
            
            logger.info(f"Found {len(mapping)} lists in category '{target_folder['name']}' (ID: {folder_id})")
            return mapping
            
        except Exception as e:
            logger.error(f"Error fetching hierarchy from Brevo: {e}")
            return {}

    def create_tables_if_dev(self):
        """Create SQLite tables for send history tracking."""
        if not self.conn:
            logger.warning("SQLite not initialized. Cannot create tables.")
            return
            
        try:
            # Create send_history table with campaign_key for job campaigns
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS send_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT NOT NULL,
                    campaign_key TEXT NOT NULL,
                    experience_level TEXT,
                    list_id INTEGER,
                    sent_at DATETIME NOT NULL,
                    status TEXT NOT NULL,
                    wamid TEXT,
                    error TEXT,
                    UNIQUE(phone, campaign_key) ON CONFLICT REPLACE
                )
            ''')
            
            # Create index for fast lookups
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_phone_campaign 
                ON send_history(phone, campaign_key, status)
            ''')
            
            self.conn.commit()
            logger.debug("Send history tables created/verified")
            
        except Exception as e:
            logger.error(f"Failed to create SQLite tables: {e}")
    
    def was_sent_before(self, phone: str, campaign_key: str) -> bool:
        """Check if phone was already successfully sent this campaign."""
        if not self.cursor:
            return False
            
        try:
            self.cursor.execute('''
                SELECT 1 FROM send_history 
                WHERE phone = ? AND campaign_key = ? AND status = 'success'
                LIMIT 1
            ''', (phone, campaign_key))
            
            return self.cursor.fetchone() is not None
            
        except Exception as e:
            logger.error(f"Error checking send history: {e}")
            return False
    
    def record_send(self, phone: str, campaign_key: str, status: str, 
                   experience_level: str = None, list_id: int = None,
                   wamid: str = None, error: str = None):
        """Record send attempt in persistent history with campaign tracking."""
        if not self.cursor:
            logger.warning("SQLite not available. Cannot record send.")
            return
            
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO send_history 
                (phone, campaign_key, experience_level, list_id, sent_at, status, wamid, error)
                VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?)
            ''', (phone, campaign_key, experience_level, list_id, status, wamid, error))
            
            self.conn.commit()
            logger.debug(f"Recorded {status} send to {phone} for campaign {campaign_key}")
            
        except Exception as e:
            logger.error(f"Failed to record send: {e}")

# Global database instance
db = BrevoClient()
