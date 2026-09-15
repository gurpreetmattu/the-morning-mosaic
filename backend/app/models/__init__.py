"""SQLAlchemy models.

Importing this package registers every table on `Base.metadata`, which is what
Alembic autogenerate reflects against.
"""

from app.models.base import Base
from app.models.content import (
    Article,
    ArticlePassage,
    ClusterArticle,
    Correction,
    Extra,
    FactCheck,
    Image,
    SentenceCitation,
    Source,
    Story,
    StoryCluster,
    StorySentence,
    StoryTag,
    StoryWithdrawal,
    WeatherCache,
)
from app.models.editions import (
    Delivery,
    Edition,
    EditionRevision,
    EditionSection,
    Feedback,
)
from app.models.operations import LlmCall, NoticeBatch, PipelineRun
from app.models.users import (
    City,
    Consent,
    FollowedKeyword,
    OutageState,
    Token,
    User,
    UserGenre,
    UserPreference,
    WaitlistEntry,
)

__all__ = [
    "Article",
    "ArticlePassage",
    "Base",
    "City",
    "ClusterArticle",
    "Consent",
    "Correction",
    "Delivery",
    "Edition",
    "EditionRevision",
    "EditionSection",
    "Extra",
    "FactCheck",
    "Feedback",
    "FollowedKeyword",
    "Image",
    "LlmCall",
    "NoticeBatch",
    "OutageState",
    "PipelineRun",
    "SentenceCitation",
    "Source",
    "Story",
    "StoryCluster",
    "StorySentence",
    "StoryTag",
    "StoryWithdrawal",
    "Token",
    "User",
    "UserGenre",
    "UserPreference",
    "WaitlistEntry",
    "WeatherCache",
]
