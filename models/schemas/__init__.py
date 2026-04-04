from .auth_schema import (
    AccessTokenResponse,
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
    ClinicalChatRequest,
    ClinicalChatResponse,
    ClinicalAlert,
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
    "AccessTokenResponse",
    "AuthResponse",
    "ProfileOut",
    # chat
    "ChatCreate",
    "ChatOut",
    "MessageCreate",
    "MessageOut",
    "AIChatRequest",
    "AIChatResponse",
    "ClinicalChatRequest",
    "ClinicalChatResponse",
    "ClinicalAlert",
    # patient
    "PatientCreate",
    "PatientOut",
    "PatientFileCreate",
    "PatientFileOut",
    "PatientHistoryCreate",
    "PatientHistoryOut",
]
