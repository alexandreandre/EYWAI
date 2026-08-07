"""Schémas du module annual_reviews (requêtes et réponses)."""

from .requests import (
    AnnualReviewBase,
    AnnualReviewCreate,
    AnnualReviewStatus,
    AnnualReviewUpdate,
    InterviewCampaignSettingsUpdate,
    InterviewType,
    SendForSignatureBody,
)
from .responses import (
    AnnualReviewListItem,
    AnnualReviewRead,
    InterviewCampaignSettingsRead,
    PlanningSuggestionRead,
)

__all__ = [
    "AnnualReviewBase",
    "AnnualReviewCreate",
    "AnnualReviewListItem",
    "AnnualReviewRead",
    "AnnualReviewStatus",
    "AnnualReviewUpdate",
    "InterviewCampaignSettingsRead",
    "InterviewCampaignSettingsUpdate",
    "InterviewType",
    "PlanningSuggestionRead",
    "SendForSignatureBody",
]
