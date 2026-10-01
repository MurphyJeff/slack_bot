"""Tests for alias detection module."""

import pytest

from group_bot.modules.groups.detector import AliasDetector


class TestAliasDetector:
    def test_basic_detection(self):
        detector = AliasDetector(["com", "bureau"])
        result = detector.detect("Bonjour la team @com j'ai ce visuel")
        assert result == ["com"]

    def test_multiple_aliases_in_message(self):
        detector = AliasDetector(["com", "bureau"])
        result = detector.detect("@com et @bureau merci")
        assert result == ["com", "bureau"]

    def test_case_insensitive(self):
        detector = AliasDetector(["com", "bureau"])
        assert detector.detect("@COM voir ce visuel") == ["com"]
        assert detector.detect("@Bureau réunion") == ["bureau"]
        assert detector.detect("@CoM test") == ["com"]

    def test_punctuation_after_alias(self):
        detector = AliasDetector(["com"])
        assert detector.detect("@com! Urgent") == ["com"]
        assert detector.detect("@com, voir ça") == ["com"]
        assert detector.detect("@com.") == ["com"]
        assert detector.detect("(@com)") == ["com"]

    def test_alias_at_start_of_message(self):
        detector = AliasDetector(["com"])
        assert detector.detect("@com bonjour") == ["com"]

    def test_alias_at_end_of_message(self):
        detector = AliasDetector(["com"])
        assert detector.detect("bonjour @com") == ["com"]

    def test_false_positive_word_continuation(self):
        detector = AliasDetector(["com"])
        assert detector.detect("@commerciale voir") == []
        assert detector.detect("@communication") == []
        assert detector.detect("@company") == []

    def test_false_positive_bureau(self):
        detector = AliasDetector(["bureau"])
        assert detector.detect("@bureautique") == []
        assert detector.detect("@bureaux") == []

    def test_no_duplicates(self):
        detector = AliasDetector(["com"])
        result = detector.detect("@com @com @com")
        assert result == ["com"]

    def test_empty_text(self):
        detector = AliasDetector(["com"])
        assert detector.detect("") == []
        assert detector.detect(None) == []

    def test_no_alias_in_text(self):
        detector = AliasDetector(["com", "bureau"])
        assert detector.detect("Bonjour la team") == []

    def test_only_at_symbol(self):
        detector = AliasDetector(["com"])
        assert detector.detect("@") == []
        assert detector.detect("@ ") == []

    def test_native_mention_ici_excluded(self):
        detector = AliasDetector(["com"])
        assert detector.detect("@ici attention") == []
        assert detector.detect("@here attention") == []

    def test_native_mention_channel_excluded(self):
        detector = AliasDetector(["com"])
        assert detector.detect("@channel attention") == []

    def test_native_mention_everyone_excluded(self):
        detector = AliasDetector(["com"])
        assert detector.detect("@everyone attention") == []

    def test_native_and_custom_in_same_message(self):
        detector = AliasDetector(["com"])
        result = detector.detect("@ici @com @here")
        assert result == ["com"]

    def test_alias_conflicting_with_native_raises(self):
        with pytest.raises(ValueError, match="conflicts with a Slack-native mention"):
            AliasDetector(["ici"])

        with pytest.raises(ValueError, match="conflicts with a Slack-native mention"):
            AliasDetector(["here"])

    def test_is_native_mention(self):
        detector = AliasDetector(["com"])
        assert detector.is_native_mention("ici") is True
        assert detector.is_native_mention("here") is True
        assert detector.is_native_mention("channel") is True
        assert detector.is_native_mention("com") is False

    def test_slack_user_mention_not_detected(self):
        detector = AliasDetector(["com"])
        assert detector.detect("<@U0C5QA76> bonjour") == []

    def test_slack_broadcast_not_detected(self):
        detector = AliasDetector(["com"])
        assert detector.detect("<!here> attention <!channel>") == []

    def test_alias_with_slack_markup_nearby(self):
        detector = AliasDetector(["com"])
        result = detector.detect("<@U123> @com regardez")
        assert result == ["com"]

    def test_single_alias(self):
        detector = AliasDetector(["com"])
        assert detector.aliases == {"com"}

    def test_no_aliases_configured(self):
        detector = AliasDetector([])
        assert detector.detect("@com bonjour") == []

    def test_order_preserved(self):
        detector = AliasDetector(["com", "bureau"])
        result = detector.detect("@bureau @com")
        assert result == ["bureau", "com"]
