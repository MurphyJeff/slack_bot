"""Tests for user resolver module."""

import pytest

from group_bot.config import GroupEntry
from group_bot.modules.groups.resolver import UserResolver


@pytest.fixture
def groups():
    return {
        "com": [
            GroupEntry(user_id="U0000001", comment="Martine"),
            GroupEntry(user_id="U0000002", comment="Alice"),
        ],
        "bureau": [
            GroupEntry(user_id="U0000003", comment="Martin"),
            GroupEntry(user_id="U0000001", comment="Martine"),  # overlap with com
        ],
    }


@pytest.fixture
def resolver(groups):
    return UserResolver(groups)


class TestUserResolver:
    def test_single_alias(self, resolver):
        result = resolver.resolve(["com"])
        assert result.user_ids == ["U0000001", "U0000002"]
        assert result.skipped_author is False
        assert result.empty_aliases == []

    def test_multiple_aliases(self, resolver):
        result = resolver.resolve(["com", "bureau"])
        assert result.user_ids == ["U0000001", "U0000002", "U0000003"]

    def test_dedup_across_aliases(self, resolver):
        result = resolver.resolve(["com", "bureau"])
        assert result.user_ids.count("U0000001") == 1

    def test_exclude_author(self, resolver):
        result = resolver.resolve(["com"], author_user_id="U0000001")
        assert result.user_ids == ["U0000002"]
        assert result.skipped_author is True

    def test_exclude_author_disabled(self, resolver):
        result = resolver.resolve(["com"], author_user_id="U0000001", exclude_author=False)
        assert result.user_ids == ["U0000001", "U0000002"]
        assert result.skipped_author is False

    def test_author_not_in_groups(self, resolver):
        result = resolver.resolve(["com"], author_user_id="U9999999")
        assert result.user_ids == ["U0000001", "U0000002"]
        assert result.skipped_author is False

    def test_no_author_id(self, resolver):
        result = resolver.resolve(["com"], author_user_id=None)
        assert result.user_ids == ["U0000001", "U0000002"]

    def test_empty_alias(self, resolver):
        result = resolver.resolve(["nonexistent"])
        assert result.user_ids == []
        assert result.empty_aliases == ["nonexistent"]

    def test_mixed_valid_and_empty(self, resolver):
        result = resolver.resolve(["com", "nonexistent"])
        assert result.user_ids == ["U0000001", "U0000002"]
        assert result.empty_aliases == ["nonexistent"]

    def test_empty_aliases_list(self, resolver):
        result = resolver.resolve([])
        assert result.user_ids == []

    def test_author_is_only_member(self):
        groups = {"solo": [GroupEntry(user_id="U0000001", comment="Solo")]}
        r = UserResolver(groups)
        result = r.resolve(["solo"], author_user_id="U0000001")
        assert result.user_ids == []
        assert result.skipped_author is True

    def test_all_members_excluded_as_author(self):
        groups = {
            "com": [GroupEntry(user_id="U0000001", comment="A")],
            "bureau": [GroupEntry(user_id="U0000001", comment="A")],
        }
        r = UserResolver(groups)
        result = r.resolve(["com", "bureau"], author_user_id="U0000001")
        assert result.user_ids == []

    def test_order_preserved(self, resolver):
        result = resolver.resolve(["bureau", "com"])
        assert result.user_ids == ["U0000003", "U0000001", "U0000002"]

    def test_no_duplicates_in_result(self, resolver):
        result = resolver.resolve(["com", "com", "com"])
        assert result.user_ids == ["U0000001", "U0000002"]
