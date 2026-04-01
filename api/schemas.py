from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class HistoryRecordCreate(BaseModel):
    kind: str
    note: str
    occurred_at: dt.datetime | None = None
    attachments: list[str] | None = None
