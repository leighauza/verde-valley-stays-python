"""
Google Calendar operations.

Replaces all 3 n8n sub-workflows (check-availability, create-booking,
cancel-booking) as plain Python functions. The CALENDAR_MAP from config.py
replaces the duplicated JS objects in each n8n workflow.

Auth:
  - First run: triggers a browser OAuth flow and saves google_token.json
  - Subsequent runs: loads and auto-refreshes the token from google_token.json
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _get_service():
    """Return an authenticated Google Calendar service object."""
    creds = None

    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.GOOGLE_TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _resolve_calendar(property_name: str) -> str | None:
    """Look up the Google Calendar ID for a given property name."""
    return config.CALENDAR_MAP.get(property_name)


# ---------------------------------------------------------------------------
# Check Availability
# ---------------------------------------------------------------------------

def check_availability(property_name: str, check_in_date: str, check_out_date: str) -> dict:
    """
    Check if a property has any existing bookings in the given date range.

    Args:
        property_name : Exact property name, e.g. "The Glasshouse"
        check_in_date : ISO date string, e.g. "2025-12-04"
        check_out_date: ISO date string, e.g. "2025-12-07"

    Returns:
        dict with keys: available (bool), property, check_in, check_out, message
    """
    calendar_id = _resolve_calendar(property_name)
    if not calendar_id:
        return {
            "available": False,
            "message": f"Unknown property: {property_name}. Please choose from the available properties.",
        }

    try:
        service = _get_service()
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id.strip(),
                timeMin=f"{check_in_date}T00:00:00Z",
                timeMax=f"{check_out_date}T23:59:59Z",
                maxResults=5,
                singleEvents=True,
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {
                "available": True,
                "property": property_name,
                "check_in": check_in_date,
                "check_out": check_out_date,
                "message": f"Yes! {property_name} is available from {check_in_date} to {check_out_date}.",
            }
        else:
            return {
                "available": False,
                "property": property_name,
                "check_in": check_in_date,
                "check_out": check_out_date,
                "message": (
                    f"Sorry, {property_name} is already booked from {check_in_date} to {check_out_date}. "
                    "Would you like to check other dates or explore our other properties?"
                ),
            }

    except Exception as e:
        logger.error(f"check_availability error: {e}")
        return {"available": False, "message": "Unable to check availability right now. Please try again."}


# ---------------------------------------------------------------------------
# Create Booking
# ---------------------------------------------------------------------------

def create_booking(
    property_name: str,
    check_in_date: str,
    check_out_date: str,
    guest_name: str,
    guest_email: str = "",
    guest_phone: str = "",
) -> dict:
    """
    Create a Google Calendar event as a booking record.

    Returns:
        dict with keys: success (bool), booking_id, property, guest_name,
                        check_in, check_out, message
    """
    calendar_id = _resolve_calendar(property_name)
    if not calendar_id:
        return {"success": False, "message": f"Unknown property: {property_name}."}

    try:
        service = _get_service()
        description_lines = [f"Guest: {guest_name}"]
        if guest_email:
            description_lines.append(f"Email: {guest_email}")
        if guest_phone:
            description_lines.append(f"Phone: {guest_phone}")

        event = {
            "summary": f"Booking: {guest_name}",
            "description": "\n".join(description_lines),
            "start": {"date": check_in_date},
            "end": {"date": check_out_date},
        }

        created_event = (
            service.events()
            .insert(calendarId=calendar_id.strip(), body=event)
            .execute()
        )
        event_id = created_event.get("id")

        return {
            "success": True,
            "booking_id": event_id,
            "property": property_name,
            "guest_name": guest_name,
            "check_in": check_in_date,
            "check_out": check_out_date,
            "message": (
                f"Booking confirmed! {guest_name} has booked {property_name} "
                f"from {check_in_date} to {check_out_date}. Confirmation ID: {event_id}"
            ),
        }

    except Exception as e:
        logger.error(f"create_booking error: {e}")
        return {"success": False, "message": "Unable to create the booking right now. Please try again."}


# ---------------------------------------------------------------------------
# Cancel Booking
# ---------------------------------------------------------------------------

def cancel_booking(property_name: str, guest_name: str, check_in_date: str) -> dict:
    """
    Find a booking event by guest name and check-in date, then delete it.

    Returns:
        dict with keys: success (bool), property, guest_name, check_in, message
    """
    calendar_id = _resolve_calendar(property_name)
    if not calendar_id:
        return {"success": False, "message": f"Unknown property: {property_name}."}

    try:
        service = _get_service()

        # Search for events on the check-in date matching the guest name
        next_day = (
            datetime.strptime(check_in_date, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        events_result = (
            service.events()
            .list(
                calendarId=calendar_id.strip(),
                timeMin=f"{check_in_date}T00:00:00Z",
                timeMax=f"{next_day}T00:00:00Z",
                q=guest_name,
                maxResults=10,
                singleEvents=True,
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return {
                "success": False,
                "property": property_name,
                "guest_name": guest_name,
                "check_in": check_in_date,
                "message": (
                    f"Sorry, I couldn't find a booking for {guest_name} at {property_name} on {check_in_date}. "
                    "Please check the details and try again, or contact us directly for assistance."
                ),
            }

        # Delete the first matching event
        event_id = events[0]["id"]
        service.events().delete(calendarId=calendar_id.strip(), eventId=event_id).execute()

        return {
            "success": True,
            "property": property_name,
            "guest_name": guest_name,
            "check_in": check_in_date,
            "message": (
                f"Booking cancelled successfully! {guest_name}'s reservation "
                f"for {property_name} on {check_in_date} has been cancelled."
            ),
        }

    except Exception as e:
        logger.error(f"cancel_booking error: {e}")
        return {"success": False, "message": "Unable to cancel the booking right now. Please try again."}
