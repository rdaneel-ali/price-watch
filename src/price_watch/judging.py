"""Code-side judgement: meets_target, suspicious, the manual listing and the best pick."""

from collections.abc import Sequence
from fractions import Fraction

from price_watch.config import SUSPICIOUS_PERCENT
from price_watch.extraction import ExtractedListing
from price_watch.models import (
    MANUAL_SOURCE_ID,
    Condition,
    Confidence,
    Listing,
    ListingStatus,
    Watch,
)

MIN_HISTORY_CHECKS = 3
MIN_OTHER_LISTINGS = 2


def median_of(values: Sequence[int]) -> Fraction | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Fraction(ordered[middle])
    return Fraction(ordered[middle - 1] + ordered[middle], 2)


def is_below_share(price: int, reference: Fraction) -> bool:
    """True when price is below SUSPICIOUS_PERCENT percent of the reference."""
    return price * 100 < reference * SUSPICIOUS_PERCENT


def find_suspicious_reasons(
    price: int,
    confidence: Confidence | None,
    history_best_prices: Sequence[int],
    other_prices: Sequence[int],
) -> list[str]:
    reasons: list[str] = []
    history_median = median_of(history_best_prices)
    if (
        len(history_best_prices) >= MIN_HISTORY_CHECKS
        and history_median is not None
        and is_below_share(price, history_median)
    ):
        reasons.append(f"below {SUSPICIOUS_PERCENT}% of the 30-day median best price")
    others_median = median_of(other_prices)
    if (
        len(other_prices) >= MIN_OTHER_LISTINGS
        and others_median is not None
        and is_below_share(price, others_median)
    ):
        reasons.append(f"below {SUSPICIOUS_PERCENT}% of the median of other matching listings")
    if confidence is Confidence.LOW:
        reasons.append("the AI has low confidence")
    return reasons


def make_manual_listing(watch: Watch) -> Listing | None:
    manual = watch.manual_price
    if manual is None:
        return None
    reason = "Entered by hand" + (f": {manual.note}" if manual.note else "")
    return Listing(
        title=f"{watch.name} (manual)",
        price=manual.price,
        condition=Condition.UNKNOWN,
        url=manual.url,
        source_id=MANUAL_SOURCE_ID,
        meets_spec=True,
        spec_reason=reason,
        ai_confidence=None,
        meets_target=manual.price <= watch.target_price,
        suspicious=False,
        status=ListingStatus.CONFIRMED,
        seen_at=manual.set_at,
    )


def make_ai_listing(
    watch: Watch, source_id: str, extracted: ExtractedListing, seen_at: str
) -> Listing:
    """Build a listing for one watch, from that watch's judgment. Suspicious comes later."""
    judgment = next(j for j in extracted.judgments if j.watch_id == watch.watch_id)
    return Listing(
        title=extracted.title,
        price=extracted.price_cents,
        condition=extracted.condition,
        url=extracted.url,
        source_id=source_id,
        meets_spec=judgment.meets_spec,
        spec_reason=judgment.spec_reason,
        ai_confidence=extracted.ai_confidence,
        meets_target=extracted.price_cents <= watch.target_price,
        suspicious=False,
        status=ListingStatus.FOUND,
        seen_at=seen_at,
    )


def flag_suspicious(
    listings: Sequence[Listing], history_best_prices: Sequence[int]
) -> list[Listing]:
    """Set `suspicious` on AI listings. The manual listing is never flagged."""
    flagged: list[Listing] = []
    for index, listing in enumerate(listings):
        if listing.source_id == MANUAL_SOURCE_ID:
            flagged.append(listing)
            continue
        others = [
            other.price
            for other_index, other in enumerate(listings)
            if other_index != index and other.meets_spec
        ]
        reasons = find_suspicious_reasons(
            listing.price, listing.ai_confidence, history_best_prices, others
        )
        flagged.append(
            listing.model_copy(
                update={
                    "suspicious": bool(reasons),
                    "suspicious_reason": "; ".join(reasons) or None,
                }
            )
        )
    return flagged


def pick_best(listings: Sequence[Listing]) -> Listing | None:
    """Cheapest listing that meets the spec and isn't suspicious. If every one that meets
    the spec is suspicious, the cheapest of those (it stays flagged). None if none meet it."""
    matching = [listing for listing in listings if listing.meets_spec]
    trusted = [listing for listing in matching if not listing.suspicious]
    pool = trusted or matching
    return min(pool, key=lambda listing: listing.price, default=None)
