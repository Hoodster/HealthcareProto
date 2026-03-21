from .auth_schema import (
    AuthResponse,
    LoginRequest,
    ProfileOut,
    RegisterRequest,
)
from .chat_schema import (
    AIChatRequest,
    AIChatResponse,
    ChatCreate,
    ChatOut,
    MessageCreate,
    MessageOut,
)
from .patient_schema import (
    PatientCreate,
    PatientFileCreate,
    PatientFileOut,
    PatientHistoryCreate,
    PatientHistoryOut,
    PatientOut,
)
from .profile_schema import *  # noqa: F401, F403

__all__ = [
    # auth
    "RegisterRequest",
    "LoginRequest",
    "AuthResponse",
    "ProfileOut",
    # chat
    "ChatCreate",
    "ChatOut",
    "MessageCreate",
    "MessageOut",
    "AIChatRequest",
    "AIChatResponse",
    # patient
    "PatientCreate",
    "PatientOut",
    "PatientFileCreate",
    "PatientFileOut",
    "PatientHistoryCreate",
    "PatientHistoryOut",
]
