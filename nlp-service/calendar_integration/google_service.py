"""
Google Calendar integration service.

Phase 4: Google Calendar Service
Updated: Real OAuth2 implementation with google-auth library
"""

import logging
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
from pathlib import Path

# Google API imports (with graceful fallback)
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    Credentials = None
    Request = None
    InstalledAppFlow = None
    build = None
    HttpError = Exception

from calendar_integration.models import (
    CalendarEvent, CalendarSync, CalendarCredentials, SyncStatus,
    CalendarProvider
)

logger = logging.getLogger(__name__)

# OAuth2 Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_DIR = Path(os.getenv('GOOGLE_TOKEN_DIR', './tokens'))
CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')


# ============================================================================
# GOOGLE CALENDAR SERVICE
# ============================================================================


class GoogleCalendarService:
    """
    Google Calendar integration service.
    Handles OAuth2 authentication and calendar operations.
    
    Environment Variables:
        GOOGLE_CREDENTIALS_FILE: Path to OAuth2 client credentials JSON
        GOOGLE_TOKEN_DIR: Directory to store user tokens
        GOOGLE_CALENDAR_MOCK_MODE: Set to 'true' to use mock implementation
    """
    
    def __init__(self, mock_mode: bool = None):
        """
        Initialize Google Calendar service.
        
        Args:
            mock_mode: Force mock mode (defaults to env var GOOGLE_CALENDAR_MOCK_MODE)
        """
        self.credentials_cache: Dict[str, Any] = {}  # Stores Credentials objects
        self.services_cache: Dict[str, Any] = {}
        
        # Check for mock mode
        if mock_mode is None:
            mock_mode = os.getenv('GOOGLE_CALENDAR_MOCK_MODE', 'false').lower() == 'true'
        self.mock_mode = mock_mode or not GOOGLE_API_AVAILABLE
        
        if not GOOGLE_API_AVAILABLE and not mock_mode:
            logger.warning(
                "Google API libraries not available. Install with: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
        
        # Ensure token directory exists
        TOKEN_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Google Calendar Service initialized (mock_mode={self.mock_mode})")
    
    def _get_token_path(self, user_email: str) -> Path:
        """Get token file path for user."""
        safe_email = user_email.replace('@', '_at_').replace('.', '_')
        return TOKEN_DIR / f"token_{safe_email}.json"
    
    def _load_credentials(self, user_email: str) -> Optional[Any]:
        """
        Load credentials from cache or file.
        
        Args:
            user_email: User's email
            
        Returns:
            Credentials if available and valid
        """
        if not GOOGLE_API_AVAILABLE:
            return None
            
        # Check cache first
        if user_email in self.credentials_cache:
            creds = self.credentials_cache[user_email]
            if creds.valid:
                return creds
            # Try to refresh if expired
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self._save_credentials(user_email, creds)
                    return creds
                except Exception as e:
                    logger.warning(f"Failed to refresh token for {user_email}: {e}")
                    del self.credentials_cache[user_email]
        
        # Try loading from file
        token_path = self._get_token_path(user_email)
        if token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                if creds.valid:
                    self.credentials_cache[user_email] = creds
                    return creds
                elif creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    self._save_credentials(user_email, creds)
                    return creds
            except Exception as e:
                logger.warning(f"Failed to load token for {user_email}: {e}")
        
        return None
    
    def _save_credentials(self, user_email: str, creds: Any) -> None:
        """Save credentials to file and cache."""
        self.credentials_cache[user_email] = creds
        token_path = self._get_token_path(user_email)
        token_path.write_text(creds.to_json())
        logger.debug(f"Saved credentials for {user_email}")
    
    def _get_service(self, user_email: str):
        """
        Get or create Google Calendar API service.
        
        Args:
            user_email: User's email
            
        Returns:
            Google Calendar service or None
        """
        if self.mock_mode:
            return None
            
        if user_email in self.services_cache:
            return self.services_cache[user_email]
        
        creds = self._load_credentials(user_email)
        if not creds:
            return None
        
        try:
            service = build('calendar', 'v3', credentials=creds)
            self.services_cache[user_email] = service
            return service
        except Exception as e:
            logger.error(f"Failed to build Calendar service: {e}")
            return None
    
    def authorize_user(self, user_email: str) -> Dict[str, Any]:
        """
        Start OAuth2 authorization flow.
        
        Args:
            user_email: User's email for identification
            
        Returns:
            Dict with authorization URL or status
        """
        if self.mock_mode:
            return {"status": "success", "message": "Mock mode - no authorization needed"}
        
        if not Path(CREDENTIALS_FILE).exists():
            return {
                "status": "error",
                "message": f"OAuth2 credentials file not found: {CREDENTIALS_FILE}"
            }
        
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            # For web apps, use flow.authorization_url() and handle callback
            # For local/desktop, use flow.run_local_server()
            creds = flow.run_local_server(port=0)
            self._save_credentials(user_email, creds)
            
            return {"status": "success", "message": f"Authorization successful for {user_email}"}
        except Exception as e:
            logger.error(f"Authorization failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def set_credentials(self, credentials: CalendarCredentials) -> bool:
        """
        Set credentials for user from CalendarCredentials model.
        Used for legacy compatibility or external token injection.
        
        Args:
            credentials: Calendar credentials
            
        Returns:
            True if successful
        """
        try:
            if self.mock_mode:
                self.credentials_cache[credentials.user_email] = credentials
                logger.info(f"Credentials set for {credentials.user_email} (mock mode)")
                return True
            
            if GOOGLE_API_AVAILABLE and credentials.access_token:
                # Create Credentials from token
                creds = Credentials(
                    token=credentials.access_token,
                    refresh_token=credentials.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.getenv('GOOGLE_CLIENT_ID'),
                    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                )
                self._save_credentials(credentials.user_email, creds)
            else:
                self.credentials_cache[credentials.user_email] = credentials
            
            logger.info(f"Credentials set for {credentials.user_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to set credentials: {e}")
            return False
    
    def create_event(
        self,
        user_email: str,
        event: CalendarEvent
    ) -> Optional[str]:
        """
        Create event in Google Calendar.
        
        Args:
            user_email: User's email
            event: Calendar event details
            
        Returns:
            Google event ID or None
        """
        try:
            # Mock mode - return fake event ID
            if self.mock_mode:
                google_event_id = f"goog_{uuid4().hex[:12]}"
                logger.info(f"Created mock event {google_event_id} in Google Calendar")
                return google_event_id
            
            # Real API mode
            service = self._get_service(user_email)
            if not service:
                logger.error(f"No service available for {user_email}")
                return None
            
            # Build event body
            body = {
                'summary': event.title,
                'description': event.description or '',
                'location': event.location or '',
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': 'UTC',
                },
            }
            
            # Add attendees if present
            if hasattr(event, 'attendee_emails') and event.attendee_emails:
                body['attendees'] = [{'email': email} for email in event.attendee_emails]
            
            # Add reminders
            if hasattr(event, 'reminder_minutes') and event.reminder_minutes:
                body['reminders'] = {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': m} for m in event.reminder_minutes
                    ]
                }
            
            # Add Google Meet for virtual appointments
            conference_data = None
            if hasattr(event, 'is_virtual') and event.is_virtual:
                body['conferenceData'] = {
                    'createRequest': {
                        'requestId': uuid4().hex,
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                    }
                }
                conference_data = True
            
            # Create event
            result = service.events().insert(
                calendarId='primary',
                body=body,
                conferenceDataVersion=1 if conference_data else 0
            ).execute()
            
            google_event_id = result.get('id')
            logger.info(f"Created event {google_event_id} in Google Calendar")
            return google_event_id
        
        except HttpError as e:
            logger.error(f"Google API error creating event: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            return None
    
    def update_event(
        self,
        user_email: str,
        event_id: str,
        event: CalendarEvent
    ) -> bool:
        """
        Update event in Google Calendar.
        
        Args:
            user_email: User's email
            event_id: Google event ID
            event: Updated event details
            
        Returns:
            True if successful
        """
        try:
            # Mock mode
            if self.mock_mode:
                logger.info(f"Updated mock event {event_id} in Google Calendar")
                return True
            
            # Real API mode
            service = self._get_service(user_email)
            if not service:
                logger.error(f"No service available for {user_email}")
                return False
            
            # Build event body
            body = {
                'summary': event.title,
                'description': event.description or '',
                'location': event.location or '',
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': 'UTC',
                },
            }
            
            if hasattr(event, 'attendee_emails') and event.attendee_emails:
                body['attendees'] = [{'email': email} for email in event.attendee_emails]
            
            service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=body
            ).execute()
            
            logger.info(f"Updated event {event_id} in Google Calendar")
            return True
        
        except HttpError as e:
            logger.error(f"Google API error updating event: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to update Google Calendar event: {e}")
            return False
    
    def delete_event(
        self,
        user_email: str,
        event_id: str
    ) -> bool:
        """
        Delete event from Google Calendar.
        
        Args:
            user_email: User's email
            event_id: Google event ID
            
        Returns:
            True if successful
        """
        try:
            # Mock mode
            if self.mock_mode:
                logger.info(f"Deleted mock event {event_id} from Google Calendar")
                return True
            
            # Real API mode
            service = self._get_service(user_email)
            if not service:
                logger.error(f"No service available for {user_email}")
                return False
            
            service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            logger.info(f"Deleted event {event_id} from Google Calendar")
            return True
        
        except HttpError as e:
            logger.error(f"Google API error deleting event: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete Google Calendar event: {e}")
            return False
    
    def list_events(
        self,
        user_email: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[List[Dict[str, Any]]]:
        """
        List events in date range.
        
        Args:
            user_email: User's email
            start_time: Range start
            end_time: Range end
            
        Returns:
            List of events or None
        """
        try:
            # Mock mode
            if self.mock_mode:
                logger.info(f"Listed mock events for {user_email} from {start_time} to {end_time}")
                return []
            
            # Real API mode
            service = self._get_service(user_email)
            if not service:
                logger.error(f"No service available for {user_email}")
                return None
            
            # Call Google Calendar API
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime',
                maxResults=100
            ).execute()
            
            events = events_result.get('items', [])
            
            logger.info(f"Listed {len(events)} events for {user_email} from {start_time} to {end_time}")
            return events
        
        except HttpError as e:
            logger.error(f"Google API error listing events: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to list Google Calendar events: {e}")
            return None
    
    def sync_appointments(
        self,
        user_email: str,
        appointments: List[CalendarEvent],
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None
    ) -> CalendarSync:
        """
        Sync appointments to Google Calendar.
        
        Args:
            user_email: User's email
            appointments: Appointments to sync
            date_range_start: Optional date range start
            date_range_end: Optional date range end
            
        Returns:
            CalendarSync record with results
        """
        sync_id = f"sync_{uuid4().hex[:12]}"
        sync_start = datetime.now()
        
        sync_record = CalendarSync(
            sync_id=sync_id,
            provider=CalendarProvider.GOOGLE,
            user_email=user_email,
            sync_from_date=date_range_start or datetime.now(),
            sync_to_date=date_range_end or (datetime.now() + timedelta(days=30))
        )
        
        try:
            successful = 0
            failed = 0
            
            for appointment in appointments:
                try:
                    # Attempt to create event
                    event_id = self.create_event(user_email, appointment)
                    
                    if event_id:
                        successful += 1
                        logger.info(f"Synced appointment {appointment.appointment_id} to Google Calendar")
                    else:
                        failed += 1
                        sync_record.sync_errors.append({
                            "appointment_id": appointment.appointment_id,
                            "error": "Failed to create event"
                        })
                
                except Exception as e:
                    failed += 1
                    sync_record.sync_errors.append({
                        "appointment_id": appointment.appointment_id,
                        "error": str(e)
                    })
            
            # Update sync record
            sync_record.total_appointments = len(appointments)
            sync_record.successful_syncs = successful
            sync_record.failed_syncs = failed
            sync_record.completed_at = datetime.now()
            
            if failed == 0:
                sync_record.sync_status = SyncStatus.SUCCESS
            elif successful > 0:
                sync_record.sync_status = SyncStatus.PARTIAL
            else:
                sync_record.sync_status = SyncStatus.FAILED
                sync_record.error_message = "All syncs failed"
            
            logger.info(
                f"Sync completed: {successful}/{len(appointments)} successful, "
                f"{failed} failed"
            )
            
            return sync_record
        
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            sync_record.sync_status = SyncStatus.FAILED
            sync_record.error_message = str(e)
            sync_record.completed_at = datetime.now()
            return sync_record


# ============================================================================
# SINGLETON PATTERN
# ============================================================================


_google_calendar_service: Optional[GoogleCalendarService] = None


def get_google_calendar_service() -> GoogleCalendarService:
    """Get or create Google Calendar service singleton."""
    global _google_calendar_service
    
    if _google_calendar_service is None:
        _google_calendar_service = GoogleCalendarService()
    
    return _google_calendar_service


def reset_google_calendar_service() -> None:
    """Reset service singleton (for testing)."""
    global _google_calendar_service
    _google_calendar_service = None
