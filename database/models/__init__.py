"""Exports Base and all 31 SQLAlchemy ORM models so Alembic discovers the entire schema."""

from database.models.base import Base
from database.models.billing import Payment, PaymentEvent, Subscription, SubscriptionPlan
from database.models.identity import AuditLog, PasswordResetToken, Role, Session, User
from database.models.markets import (
    Exchange,
    Instrument,
    Market,
    MarketCalendarOverride,
    MarketData,
    ProviderStatus,
)
from database.models.signals import (
    CompanyFundamental,
    CongressDisclosure,
    MarketNews,
    SignalOutcome,
    SignalUpdate,
    SkillRun,
    SystemSetting,
    TradingSignal,
    WorkflowRun,
)
from database.models.workspace import (
    Alert,
    Notification,
    NotificationPreference,
    UserPreference,
    UserTradingJournal,
    Watchlist,
    WatchlistItem,
)

__all__ = [
    "Base",
    "Role",
    "User",
    "Session",
    "PasswordResetToken",
    "AuditLog",
    "SubscriptionPlan",
    "Subscription",
    "Payment",
    "PaymentEvent",
    "Market",
    "Exchange",
    "MarketCalendarOverride",
    "Instrument",
    "MarketData",
    "ProviderStatus",
    "SystemSetting",
    "WorkflowRun",
    "SkillRun",
    "TradingSignal",
    "SignalUpdate",
    "SignalOutcome",
    "MarketNews",
    "CompanyFundamental",
    "CongressDisclosure",
    "Watchlist",
    "WatchlistItem",
    "UserPreference",
    "UserTradingJournal",
    "Alert",
    "NotificationPreference",
    "Notification",
]
