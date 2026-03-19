from api.schemas.auth_schema import (
    AuthResponse,
    LoginRequest,
    ProfileOut,
    RegisterRequest,
)
from api.schemas.chat_schema import (
    AIChatRequest,
    AIChatResponse,
    ChatCreate,
    ChatOut,
    MessageCreate,
    MessageOut,
)
from api.schemas.patient_schema import (
    PatientCreate,
    PatientFileCreate,
    PatientFileOut,
    PatientHistoryCreate,
    PatientHistoryOut,
    PatientOut,
)
from api.schemas.profile_schema import *  # noqa: F401, F403

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
