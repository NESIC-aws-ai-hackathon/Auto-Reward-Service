"""
VoiceSessionService - DEPRECATED. Replaced by sonic_voice_session.py
This module is kept only for backward compatibility of imports.
All functionality now uses Amazon Nova Sonic via Bedrock.
"""
from services.sonic_voice_session import SonicVoiceSessionService as VoiceSessionService

__all__ = ["VoiceSessionService"]
