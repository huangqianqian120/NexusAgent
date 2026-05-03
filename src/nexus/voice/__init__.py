"""Voice exports."""

from nexus.voice.keyterms import extract_keyterms
from nexus.voice.stream_stt import transcribe_stream
from nexus.voice.voice_mode import VoiceDiagnostics, inspect_voice_capabilities, toggle_voice_mode

__all__ = [
    "VoiceDiagnostics",
    "extract_keyterms",
    "inspect_voice_capabilities",
    "toggle_voice_mode",
    "transcribe_stream",
]
