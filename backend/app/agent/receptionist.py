import asyncio
import json
import logging

from livekit.agents import Agent, RunContext, function_tool

from app.config import settings
from app.prompts.receptionist import build_system_prompt
from app.services.booking_service import (
    CLINIC_TZ,
    book_appointment as db_book_appointment,
    check_availability as db_check_availability,
)
from app.services.booking_session import (
    BookingSessionState,
    BookingStateLockedError,
)
from app.services.embedding_service import RagUnavailableError
from app.services.knowledge_service import search_knowledge

logger = logging.getLogger("clinic-booking-agent")


class ClinicReceptionist(Agent):
    def __init__(
        self,
        call_id: str,
        today: str,
        clinic_name: str,
        clinic_details: str,
        doctor_roster: str,
    ):
        self._base_instructions = build_system_prompt(
            clinic_name=clinic_name,
            clinic_details=clinic_details,
            doctor_roster=doctor_roster,
            today=today,
            timezone=CLINIC_TZ.key,
        )
        self.booking_state = BookingSessionState()
        self._last_state_summary = self.booking_state.prompt_summary()
        super().__init__(instructions=self._compose_instructions())
        self.call_id = call_id

    def _compose_instructions(self) -> str:
        return (
            f"{self._base_instructions}\n\n"
            f"{self.booking_state.prompt_summary()}"
        )

    def _json_with_state(self, payload: dict) -> str:
        result = dict(payload)
        result["session_state"] = self.booking_state.prompt_summary()
        return json.dumps(result, default=str)

    async def _refresh_instructions(self) -> None:
        summary = self.booking_state.prompt_summary()
        if summary == self._last_state_summary:
            return

        try:
            await self.update_instructions(self._compose_instructions())
        except Exception:
            logger.exception("Could not refresh booking session state")
            return
        self._last_state_summary = summary

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        await self._refresh_instructions()

    @function_tool()
    async def save_booking_details(
        self,
        context: RunContext,
        date: str = "",
        doctor: str = "",
        name: str = "",
        phone: str = "",
    ) -> str:
        """Remember booking details the caller has already provided.

        Use this immediately when the caller states or corrects a booking
        detail that is not being passed to check_availability or
        book_appointment in the same turn. Omit or pass an empty string for
        each detail that was not provided in this turn.

        Args:
            date: Requested appointment date in YYYY-MM-DD format.
            doctor: Doctor's name, for example Dr. Sharma.
            name: Patient's full name.
            phone: Patient's phone number.
        """
        if not any((date, doctor, name, phone)):
            return self._json_with_state(
                {
                    "ok": False,
                    "message": "No booking detail was provided to save.",
                }
            )

        try:
            self.booking_state.update_details(
                date=date or None,
                doctor=doctor or None,
                name=name or None,
                phone=phone or None,
            )
        except BookingStateLockedError:
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "BOOKING_ALREADY_CONFIRMED",
                    "message": (
                        "The appointment is already confirmed. Do not collect "
                        "or change booking details; refer changes to staff."
                    ),
                }
            )
        except ValueError as exc:
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "INVALID_BOOKING_DETAIL",
                    "message": str(exc),
                }
            )

        return self._json_with_state(
            {
                "ok": True,
                "message": (
                    "Booking details saved. Ask only for the next missing "
                    "detail and do not ask for saved details again."
                ),
            }
        )

    @function_tool()
    async def check_availability(
        self,
        context: RunContext,
        date: str,
        doctor: str,
    ) -> str:
        """Check real available appointment slots.

        Args:
            date: Requested date in YYYY-MM-DD format.
            doctor: Doctor's name, for example Dr. Sharma.
        """
        try:
            self.booking_state.update_details(date=date, doctor=doctor)
        except BookingStateLockedError:
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "BOOKING_ALREADY_CONFIRMED",
                    "message": (
                        "The appointment is already confirmed. Do not check "
                        "availability again; refer changes to staff."
                    ),
                }
            )
        except ValueError as exc:
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "INVALID_DATE",
                    "message": str(exc),
                }
            )

        try:
            result = await asyncio.wait_for(
                db_check_availability(date, doctor),
                timeout=settings.availability_timeout_seconds,
            )
            self.booking_state.record_availability(result)
            return self._json_with_state(result)

        except Exception:
            logger.exception("Availability tool failed")
            self.booking_state.record_availability_error()
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "AVAILABILITY_ERROR",
                    "message": (
                        "Availability service is temporarily unavailable. "
                        "Tell the caller you cannot verify availability."
                    ),
                }
            )

    @function_tool()
    async def book_appointment(
        self,
        context: RunContext,
        name: str,
        phone: str,
        slot_id: str,
        confirmed: bool,
    ) -> str:
        """Book a slot only after the caller explicitly confirms.

        Args:
            name: Patient's full name.
            phone: Patient's phone number.
            slot_id: Exact slot_id returned by check_availability.
            confirmed: True only after the caller explicitly agrees
                to book the repeated appointment details.
        """
        if confirmed is not True:
            return self._json_with_state(
                {
                    "ok": False,
                    "message": (
                        "Booking not attempted. Confirm the appointment "
                        "details with the caller first."
                    ),
                }
            )

        selected_slot = next(
            (
                slot
                for slot in self.booking_state.available_slots
                if slot["slot_id"] == slot_id
            ),
            None,
        )
        if selected_slot is None:
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "INVALID_SLOT",
                    "message": (
                        "That slot was not returned by the current "
                        "availability check. Check availability again before "
                        "booking."
                    ),
                }
            )
        try:
            self.booking_state.record_booking_attempt(
                name=name,
                phone=phone,
                slot_id=slot_id,
                local_time=(
                    selected_slot["local_time"] if selected_slot else None
                ),
            )
        except BookingStateLockedError:
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "BOOKING_ALREADY_CONFIRMED",
                    "message": (
                        "The appointment is already confirmed. Do not book "
                        "again; refer changes to staff."
                    ),
                }
            )

        try:
            result = await asyncio.wait_for(
                db_book_appointment(
                    name=name,
                    phone=phone,
                    slot_id=slot_id,
                    call_id=self.call_id,
                ),
                timeout=settings.booking_timeout_seconds,
            )
            self.booking_state.record_booking(result)
            return self._json_with_state(result)

        except Exception:
            logger.exception("Booking tool failed")
            self.booking_state.record_booking_error()
            return self._json_with_state(
                {
                    "ok": False,
                    "code": "BOOKING_ERROR",
                    "message": (
                        "Booking could not be verified. Do not claim "
                        "success. Check the booking state before retrying."
                    ),
                }
            )

    @function_tool()
    async def search_clinic_knowledge(
        self,
        context: RunContext,
        query: str,
    ) -> str:
        """Search admin-managed clinic FAQ knowledge.

        Args:
            query: The caller's clinic FAQ question or topic.
        """
        cleaned = " ".join((query or "").split())
        if not cleaned:
            return json.dumps(
                {
                    "ok": False,
                    "message": "Provide a clinic FAQ topic to search.",
                }
            )

        try:
            results = await asyncio.wait_for(
                search_knowledge(cleaned),
                timeout=settings.rag_timeout_seconds,
            )
            return json.dumps(
                {
                    "ok": True,
                    "results": results,
                    "message": (
                        "Answer only from these results. If they do not "
                        "answer the question, say clinic staff will confirm."
                    ),
                },
                default=str,
            )
        except RagUnavailableError:
            return json.dumps(
                {
                    "ok": False,
                    "message": (
                        "Clinic knowledge search is unavailable. "
                        "Say clinic staff will confirm."
                    ),
                }
            )
        except Exception:
            logger.exception("Clinic knowledge search failed")
            return json.dumps(
                {
                    "ok": False,
                    "message": (
                        "Clinic knowledge search failed. Say clinic staff "
                        "will confirm. Do not invent an answer."
                    ),
                }
            )
