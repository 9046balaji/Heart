"""
Microsoft Outlook Calendar integration service.

Phase 4: Outlook Calendar Service
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4

from calendar_integration.models import (
    CalendarEvent, CalendarSync, CalendarCredentials, SyncStatus,
    CalendarProvider
)

logger = logging.getLogger(__name__)


# ============================================================================
# OUTLOOK CALENDAR SERVICE
# ============================================================================


class OutlookCalendarService:
    """
    Microsoft Outlook Calendar integration service.
    Uses Microsoft Graph API for calendar operations.
    """
    
    def __init__(self):
        """Initialize Outlook Calendar service."""
        self.credentials_cache: Dict[str, CalendarCredentials] = {}
        self.graph_client = None
        logger.info("Outlook Calendar Service initialized")
    
    def set_credentials(self, credentials: CalendarCredentials) -> bool:
        """
        Set credentials for user.
        
        Args:
            credentials: Calendar credentials
            
        Returns:
            True if successful
        """
        try:
            # In production: validate token with Microsoft Graph
            # headers = {'Authorization': f'Bearer {credentials.access_token}'}
            # response = requests.get(GRAPH_ME_URL, headers=headers)
            # user_info = response.json()
            
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
        Create event in Outlook Calendar.
        
        Args:
            user_email: User's email
            event: Calendar event details
            
        Returns:
            Outlook event ID or None
        """
        try:
            credentials = self.credentials_cache.get(user_email)
            if not credentials:
                logger.error(f"No credentials for {user_email}")
                return None
            
            # In production: use Microsoft Graph API
            # headers = {'Authorization': f'Bearer {credentials.access_token}'}
            # body = {
            #     'subject': event.title,
            #     'bodyPreview': event.description,
            #     'start': {
            #         'dateTime': event.start_time.isoformat(),
            #         'timeZone': 'UTC'
            #     },
            #     'end': {
            #         'dateTime': event.end_time.isoformat(),
            #         'timeZone': 'UTC'
            #     },
            #     'location': {'displayName': event.location},
            #     'attendees': [
            #         {
            #             'emailAddress': {'address': email},
            #             'type': 'required'
            #         } for email in event.attendee_emails
            #     ],
            #     'isReminderOn': True,
            #     'reminderMinutesBeforeStart': min(event.reminder_minutes)
            # }
            # result = requests.post(
            #     f'{GRAPH_API_URL}/me/calendar/events',
            #     headers=headers,
            #     json=body
            # ).json()
            
            # Mock implementation
            outlook_event_id = f"outl_{uuid4().hex[:12]}"
            logger.info(f"Created event {outlook_event_id} in Outlook Calendar")
            return outlook_event_id
        
        except Exception as e:
            logger.error(f"Failed to create Outlook Calendar event: {e}")
            return None
    
    def update_event(
        self,
        user_email: str,
        event_id: str,
        event: CalendarEvent
    ) -> bool:
        """
        Update event in Outlook Calendar.
        
        Args:
            user_email: User's email
            event_id: Outlook event ID
            event: Updated event details
            
        Returns:
            True if successful
        """
        try:
            credentials = self.credentials_cache.get(user_email)
            if not credentials:
                logger.error(f"No credentials for {user_email}")
                return False
            
            # In production: use Microsoft Graph API
            # headers = {'Authorization': f'Bearer {credentials.access_token}'}
            # body = {...}  # Same as create_event
            # requests.patch(
            #     f'{GRAPH_API_URL}/me/calendar/events/{event_id}',
            #     headers=headers,
            #     json=body
            # )
            
            logger.info(f"Updated event {event_id} in Outlook Calendar")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update Outlook Calendar event: {e}")
            return False
    
    def delete_event(
        self,
        user_email: str,
        event_id: str
    ) -> bool:
        """
        Delete event from Outlook Calendar.
        
        Args:
            user_email: User's email
            event_id: Outlook event ID
            
        Returns:
            True if successful
        """
        try:
            credentials = self.credentials_cache.get(user_email)
            if not credentials:
                logger.error(f"No credentials for {user_email}")
                return False
            
            # In production: use Microsoft Graph API
            # headers = {'Authorization': f'Bearer {credentials.access_token}'}
            # requests.delete(
            #     f'{GRAPH_API_URL}/me/calendar/events/{event_id}',
            #     headers=headers
            # )
            
            logger.info(f"Deleted event {event_id} from Outlook Calendar")
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete Outlook Calendar event: {e}")
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
            credentials = self.credentials_cache.get(user_email)
            if not credentials:
                logger.error(f"No credentials for {user_email}")
                return None
            
            # In production: use Microsoft Graph API
            # headers = {'Authorization': f'Bearer {credentials.access_token}'}
            # params = {
            #     'startDateTime': start_time.isoformat(),
            #     'endDateTime': end_time.isoformat()
            # }
            # events_result = requests.get(
            #     f'{GRAPH_API_URL}/me/calendarview',
            #     headers=headers,
            #     params=params
            # ).json()
            
            logger.info(f"Listed events for {user_email} from {start_time} to {end_time}")
            return []  # Mock implementation
        
        except Exception as e:
            logger.error(f"Failed to list Outlook Calendar events: {e}")
            return None
    
    def sync_appointments(
        self,
        user_email: str,
        appointments: List[CalendarEvent],
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None
    ) -> CalendarSync:
        """
        Sync appointments to Outlook Calendar.
        
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
            provider=CalendarProvider.OUTLOOK,
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
                        logger.info(f"Synced appointment {appointment.appointment_id} to Outlook Calendar")
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


_outlook_calendar_service: Optional[OutlookCalendarService] = None


def get_outlook_calendar_service() -> OutlookCalendarService:
    """Get or create Outlook Calendar service singleton."""
    global _outlook_calendar_service
    
    if _outlook_calendar_service is None:
        _outlook_calendar_service = OutlookCalendarService()
    
    return _outlook_calendar_service


def reset_outlook_calendar_service() -> None:
    """Reset service singleton (for testing)."""
    global _outlook_calendar_service
    _outlook_calendar_service = None
