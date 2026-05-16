import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import flet as ft
from flet.controls.control_event import ControlEventHandler

logger = logging.getLogger("flet_stt")


class SttError(Exception):
    """Raised when a speech-to-text operation fails on the native side."""

    pass


@dataclass
class SttResult:
    """Parsed speech recognition result.

    Usage:
        def on_result(e):
            r = SttResult(e)
            print(r.text, r.final, r.confidence)
    """

    text: str
    final: bool
    confidence: float
    alternates: list[dict] = field(default_factory=list)

    def __init__(self, event):
        data = json.loads(event.data)
        self.text = data["text"]
        self.final = data["final"]
        self.confidence = data["confidence"]
        self.alternates = data.get("alternates", [])


@dataclass
class SttErrorData:
    """Parsed speech recognition error.

    Usage:
        def on_error(e):
            err = SttErrorData(e)
            print(err.error, err.permanent)
    """

    error: str
    permanent: bool

    def __init__(self, event):
        data = json.loads(event.data)
        self.error = data["error"]
        self.permanent = data["permanent"]


@dataclass
class SttStatus:
    """Parsed speech recognition status change.

    Usage:
        def on_status(e):
            s = SttStatus(e)
            print(s.status)  # "listening", "notListening", or "done"
    """

    status: str

    def __init__(self, event):
        data = json.loads(event.data)
        self.status = data["status"]

    @property
    def listening(self) -> bool:
        return self.status == "listening"

    @property
    def done(self) -> bool:
        return self.status == "done"


@dataclass
class SttSoundLevel:
    """Parsed microphone sound level.

    Usage:
        def on_sound_level(e):
            s = SttSoundLevel(e)
            print(s.level)  # raw dB, e.g. -6.5
    """

    level: float

    def __init__(self, event):
        data = json.loads(event.data)
        self.level = data["level"]


@ft.control("flet_stt")
class FletStt(ft.Service):
    """Speech-to-text service using OS-native recognition.

    WARNING: do not add this to page.overlay, page.controls, or page.add().
    It registers itself automatically. Adding it to the UI tree causes a
    red crash screen on Android with no useful error message.

    Correct usage:
        stt = FletStt()
        stt.on_result = my_handler
        await stt.initialize()
        await stt.listen()

    Wraps the Flutter speech_to_text package. On Android this uses Google
    Speech Services (on-device for ~50 languages). On iOS it uses Apple's
    SFSpeechRecognizer.

    Events:
        on_result: Fires with recognition results.
            e.data is JSON: {"text": "hello", "final": true, "confidence": 0.95}
        on_sound_level: Fires with microphone dB level during listening.
            e.data is JSON: {"level": -6.5}
        on_error: Fires on recognition errors.
            e.data is JSON: {"error": "error_speech_timeout", "permanent": false}
        on_status: Fires on status changes.
            e.data is JSON: {"status": "listening"} or {"status": "notListening"} or {"status": "done"}
    """

    on_result: Optional[ControlEventHandler["FletStt"]] = None
    on_sound_level: Optional[ControlEventHandler["FletStt"]] = None
    on_error: Optional[ControlEventHandler["FletStt"]] = None
    on_status: Optional[ControlEventHandler["FletStt"]] = None

    _initialized: bool = False

    def _check_error(self, result):
        """Check if Dart returned an error and raise if so."""
        if isinstance(result, str) and result.startswith("error:"):
            raise SttError(result[6:])
        if result is None:
            logger.warning("service returned None (is the extension registered?)")
        return result

    async def initialize(self) -> bool:
        """Initialize the speech recognizer and check availability.

        Must be called before listen(). Requests microphone permission
        on first call.

        Returns:
            True if speech recognition is available, False otherwise.

        Raises:
            SttError: If initialization fails on the native side.
        """
        result = await self._invoke_method(method_name="initialize")
        checked = self._check_error(result)
        if checked == "true":
            self._initialized = True
            return True
        if result is None:
            return False
        perm = await self.has_permission()
        if not perm:
            raise SttError("microphone permission denied - grant RECORD_AUDIO permission and try again")
        logger.info("speech recognition unavailable on this device")
        return False

    async def listen(
        self,
        *,
        locale_id: str = "",
        listen_for_seconds: int = 0,
        pause_for_seconds: int = 0,
        partial_results: bool = True,
        on_device: bool = False,
        cancel_on_error: bool = False,
        sample_rate: int = 0,
        listen_mode: str = "confirmation",
        auto_punctuation: bool = False,
        enable_haptic_feedback: bool = False,
        cloud_timeout_seconds: int = 15,
    ) -> None:
        """Start listening for speech.

        Args:
            locale_id: BCP-47 locale (e.g. "en_US", "ro_RO"). Empty = system default.
            listen_for_seconds: Max listen duration in seconds. 0 = platform default
                (typically ~60s on Android before auto-stop).
            pause_for_seconds: Auto-stop after this many seconds of silence. 0 = platform default.
            partial_results: If True, on_result fires for partial (non-final) results
                during recognition, not just the final result.
            on_device: Use on-device recognition. Default is False (cloud) because
                on-device models may not be installed and fail silently with no results.
            cancel_on_error: If True, cancel recognition on error instead of continuing.
            sample_rate: Audio sample rate in Hz. 0 = platform default.
            listen_mode: Recognition mode. One of:
                - "confirmation": short phrases, yes/no responses (default)
                - "search": search query input
                - "dictation": longer free-form text
            auto_punctuation: Automatically insert punctuation (iOS only, no-op on Android).
            enable_haptic_feedback: Haptic feedback while listening (iOS only, no-op on Android).
            cloud_timeout_seconds: Seconds to wait for cloud recognition before firing a
                cloud_recognition_timeout error. 0 = no timeout. Only applies when
                on_device=False. Default is 15.

        Raises:
            SttError: If listening fails to start.
        """
        if not self._initialized:
            raise SttError("call initialize() before listen()")
        result = await self._invoke_method(
            method_name="listen",
            arguments={
                "locale_id": locale_id,
                "listen_for_seconds": listen_for_seconds,
                "pause_for_seconds": pause_for_seconds,
                "partial_results": partial_results,
                "on_device": on_device,
                "cancel_on_error": cancel_on_error,
                "sample_rate": sample_rate,
                "listen_mode": listen_mode,
                "auto_punctuation": auto_punctuation,
                "enable_haptic_feedback": enable_haptic_feedback,
                "cloud_timeout_seconds": cloud_timeout_seconds,
            },
        )
        self._check_error(result)
        if result is not None and result != "ok":
            logger.debug("listen() returned unexpected: %s", result)

    async def stop(self) -> None:
        """Stop listening and trigger the final recognition result.

        After calling stop(), you'll receive one last on_result event with
        final=True containing the complete recognized text.

        Raises:
            SttError: If the stop operation fails.
        """
        if not self._initialized:
            raise SttError("call initialize() before stop()")
        result = await self._invoke_method(method_name="stop")
        self._check_error(result)
        if result is not None and result != "ok":
            logger.debug("stop() returned unexpected: %s", result)

    async def cancel(self) -> None:
        """Cancel listening without triggering a final result.

        Use this when the user wants to discard the current recognition
        session entirely.

        Raises:
            SttError: If the cancel operation fails.
        """
        if not self._initialized:
            raise SttError("call initialize() before cancel()")
        result = await self._invoke_method(method_name="cancel")
        self._check_error(result)
        if result is not None and result != "ok":
            logger.debug("cancel() returned unexpected: %s", result)

    async def change_pause_for(self, seconds: int) -> None:
        """Change the silence timeout while listening.

        Restarts the pause timer with the new duration. Useful for allowing
        a long initial pause then shortening it once the user starts speaking.

        Must be called while actively listening (after listen(), before stop/cancel).

        Args:
            seconds: New silence timeout in seconds.

        Raises:
            SttError: If not initialized or not currently listening.
        """
        if not self._initialized:
            raise SttError("call initialize() before change_pause_for()")
        result = await self._invoke_method(method_name="change_pause_for", arguments=seconds)
        self._check_error(result)

    async def system_locale(self) -> dict:
        """Get the system's default speech recognition locale.

        Returns:
            Dict with "id" and "name" keys, e.g. {"id": "en_US", "name": "English (United States)"}.

        Raises:
            SttError: If the query fails.
        """
        result = await self._invoke_method(method_name="system_locale")
        self._check_error(result)
        if result is None:
            raise SttError("extension not registered - system_locale unavailable")
        return json.loads(result)

    async def is_listening(self) -> bool:
        """Check whether the speech recognizer is currently listening.

        Returns:
            True if actively listening, False otherwise.
        """
        result = await self._invoke_method(method_name="is_listening")
        self._check_error(result)
        return result == "true"

    async def has_permission(self) -> bool:
        """Check whether the app has microphone permission.

        Returns:
            True if permission is granted, False otherwise.
        """
        result = await self._invoke_method(method_name="has_permission")
        self._check_error(result)
        return result == "true"

    async def locales(self) -> list[dict]:
        """Get available speech recognition locales.

        Returns:
            List of dicts, each with "id" and "name" keys.
            Example: [{"id": "en_US", "name": "English (United States)"}, ...]

        Raises:
            SttError: If the query fails.
        """
        result = await self._invoke_method(method_name="locales")
        self._check_error(result)
        if result is None:
            raise SttError("extension not registered - locales unavailable")
        return json.loads(result)
