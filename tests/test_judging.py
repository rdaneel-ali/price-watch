from fractions import Fraction

from price_watch.extraction import ExtractedListing, WatchJudgment
from price_watch.judging import (
    find_suspicious_reasons,
    flag_suspicious,
    make_ai_listing,
    make_manual_listing,
    median_of,
    pick_best,
)
from price_watch.models import Condition, Confidence, Listing, ListingStatus
from tests.helpers import NOW, make_watch


def listing(price: int, *, spec: bool = True, suspicious: bool = False, sid: str = "s0") -> Listing:
    return Listing(
        title="t",
        price=price,
        condition=Condition.NEW,
        url="https://x.example.com/1",
        source_id=sid,
        meets_spec=spec,
        spec_reason="r",
        ai_confidence=Confidence.HIGH,
        meets_target=True,
        suspicious=suspicious,
        status=ListingStatus.FOUND,
        seen_at=NOW,
    )


def test_median() -> None:
    assert median_of([]) is None
    assert median_of([3, 1, 2]) == 2
    assert median_of([1, 2]) == Fraction(3, 2)


def test_history_rule_needs_three_checks_and_is_strictly_below_sixty_percent() -> None:
    assert find_suspicious_reasons(59, Confidence.HIGH, [100, 100, 100], [])
    assert not find_suspicious_reasons(60, Confidence.HIGH, [100, 100, 100], [])
    assert not find_suspicious_reasons(10, Confidence.HIGH, [100, 100], [])


def test_other_listings_rule_needs_two_others() -> None:
    assert find_suspicious_reasons(50, Confidence.HIGH, [], [100, 100])
    assert not find_suspicious_reasons(50, Confidence.HIGH, [], [100])
    assert not find_suspicious_reasons(60, Confidence.HIGH, [], [100, 100])


def test_low_confidence_is_suspicious() -> None:
    assert find_suspicious_reasons(100, Confidence.LOW, [], []) == ["the AI has low confidence"]


def test_flag_suspicious_uses_other_matching_listings_only() -> None:
    listings = [listing(50), listing(100), listing(100), listing(10, spec=False)]
    flagged = flag_suspicious(listings, [])
    assert [item.suspicious for item in flagged] == [True, False, False, True]
    assert flagged[0].suspicious_reason is not None
    assert flagged[1].suspicious_reason is None


def test_manual_listing_never_flagged() -> None:
    watch = make_watch(manual={"price": 1000, "set_at": NOW, "note": "store clerk"})
    manual = make_manual_listing(watch)
    assert manual is not None
    assert manual.spec_reason == "Entered by hand: store clerk"
    assert manual.status is ListingStatus.CONFIRMED
    flagged = flag_suspicious([manual, listing(100000), listing(100000)], [])
    assert not flagged[0].suspicious


def test_no_manual_price_gives_none() -> None:
    assert make_manual_listing(make_watch()) is None


def test_make_ai_listing_sets_meets_target_by_code() -> None:
    watch = make_watch(target=1000)
    extracted = ExtractedListing(
        title="t",
        price_cents=1000,
        condition=Condition.NEW,
        url="https://x.example.com/1",
        ai_confidence=Confidence.HIGH,
        judgments=(WatchJudgment(watch_id="w1", meets_spec=True, spec_reason="ok"),),
    )
    made = make_ai_listing(watch, "s0", extracted, NOW)
    assert made.meets_target and not made.suspicious
    assert made.status is ListingStatus.FOUND


def test_best_is_cheapest_trusted_matching() -> None:
    items = [listing(100, suspicious=True), listing(200), listing(150, spec=False), listing(300)]
    best = pick_best(items)
    assert best is not None and best.price == 200


def test_best_falls_back_to_cheapest_suspicious() -> None:
    items = [listing(100, suspicious=True), listing(90, suspicious=True), listing(5, spec=False)]
    best = pick_best(items)
    assert best is not None and best.price == 90 and best.suspicious


def test_best_none_when_nothing_matches() -> None:
    assert pick_best([listing(100, spec=False)]) is None
    assert pick_best([]) is None
