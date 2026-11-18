"""Timezone utilities with ZoneInfo primary and exact stdlib fallbacks for IST and US Eastern."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class _IndiaStandardTime(tzinfo):
    """Fixed UTC+05:30 timezone for Asia/Kolkata (India does not observe DST)."""

    _OFFSET = timedelta(hours=5, minutes=30)

    def utcoffset(self, dt: datetime | None) -> timedelta:
        return self._OFFSET

    def dst(self, dt: datetime | None) -> timedelta:
        return timedelta(0)

    def tzname(self, dt: datetime | None) -> str:
        return "IST"


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Return the n-th occurrence (1-indexed) of weekday (0=Mon..6=Sun) in given month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + (n - 1) * 7)


class _USEasternTime(tzinfo):
    """Exact America/New_York timezone obeying US Energy Policy Act of 2005 DST rules.

    DST starts on the 2nd Sunday of March at 02:00 local time (UTC-5 -> UTC-4)
    and ends on the 1st Sunday of November at 02:00 local time (UTC-4 -> UTC-5).
    """

    _STD_OFFSET = timedelta(hours=-5)
    _DST_OFFSET = timedelta(hours=-4)

    def _is_dst(self, dt: datetime | None) -> bool:
        if dt is None:
            return False
        year = dt.year
        dst_start = datetime.combine(
            _nth_weekday_of_month(year, 3, 6, 2), datetime.min.time()
        ) + timedelta(hours=2)
        dst_end = datetime.combine(
            _nth_weekday_of_month(year, 11, 6, 1), datetime.min.time()
        ) + timedelta(hours=2)

        naive = dt.replace(tzinfo=None)
        if dt.fold == 1:
            # Post-fallback ambiguous hour (01:00–02:00 on 1st Sunday Nov) is EST
            if dst_end - timedelta(hours=1) <= naive < dst_end:
                return False
        return dst_start <= naive < dst_end

    def utcoffset(self, dt: datetime | None) -> timedelta:
        return self._DST_OFFSET if self._is_dst(dt) else self._STD_OFFSET

    def dst(self, dt: datetime | None) -> timedelta:
        return timedelta(hours=1) if self._is_dst(dt) else timedelta(0)

    def tzname(self, dt: datetime | None) -> str:
        return "EDT" if self._is_dst(dt) else "EST"

    def fromutc(self, dt: datetime) -> datetime:
        """Convert a UTC datetime cleanly into local EST/EDT with correct fold."""
        if dt.tzinfo is not self:
            raise ValueError("fromutc: dt.tzinfo is not self")
        utc_naive = dt.replace(tzinfo=None)
        year = utc_naive.year
        # 02:00 EST == 07:00 UTC on 2nd Sunday of March
        dst_start_utc = datetime.combine(
            _nth_weekday_of_month(year, 3, 6, 2), datetime.min.time()
        ) + timedelta(hours=7)
        # 02:00 EDT == 06:00 UTC on 1st Sunday of November
        dst_end_utc = datetime.combine(
            _nth_weekday_of_month(year, 11, 6, 1), datetime.min.time()
        ) + timedelta(hours=6)

        if dst_start_utc <= utc_naive < dst_end_utc:
            return (utc_naive + self._DST_OFFSET).replace(tzinfo=self, fold=0)
        # Check if inside the 1-hour post-fallback fold window (06:00–07:00 UTC)
        fold = 1 if dst_end_utc <= utc_naive < dst_end_utc + timedelta(hours=1) else 0
        return (utc_naive + self._STD_OFFSET).replace(tzinfo=self, fold=fold)


_FALLBACK_ZONES: dict[str, tzinfo] = {
    "UTC": timezone.utc,
    "Asia/Kolkata": _IndiaStandardTime(),
    "America/New_York": _USEasternTime(),
}


def get_timezone(tz_name: str) -> tzinfo:
    """Return ZoneInfo(tz_name) if IANA tzdata is installed, else exact built-in tzinfo."""
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        if tz_name in _FALLBACK_ZONES:
            return _FALLBACK_ZONES[tz_name]
        raise
