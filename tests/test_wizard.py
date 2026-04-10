"""Tests for skopus.wizard."""

from skopus.wizard import (
    DEFAULT_NON_NEGOTIABLES_BY_ROLE,
    WizardResult,
    default_result,
)


def test_wizard_result_as_context_has_date_and_time():
    result = WizardResult(name="Alice")
    ctx = result.as_context()
    assert ctx["name"] == "Alice"
    assert "date" in ctx
    assert "time" in ctx
    assert len(ctx["date"]) == 10  # YYYY-MM-DD
    assert len(ctx["time"]) == 5  # HH:MM


def test_default_result_seeds_non_negotiables_from_role():
    result = default_result(name="Bob", seed_profile="bug-hunter")
    assert result.name == "Bob"
    assert result.seed_profile == "bug-hunter"
    assert result.role == "bug-hunter"
    assert result.non_negotiables == DEFAULT_NON_NEGOTIABLES_BY_ROLE["bug-hunter"]


def test_default_result_blank_profile_falls_back_to_other():
    result = default_result(name="Carol", seed_profile="blank")
    assert result.role == "other"
    assert result.non_negotiables == DEFAULT_NON_NEGOTIABLES_BY_ROLE["other"]


def test_default_result_all_known_profiles_have_non_negotiables():
    for profile in ["solo-dev", "team-lead", "engineering-manager", "research", "founder", "bug-hunter"]:
        result = default_result(seed_profile=profile)
        assert len(result.non_negotiables) >= 3, f"profile {profile} has too few non-negotiables"
