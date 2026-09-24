"""Capability classifier tests.

The taxonomy constraint is the thing worth guarding: the model must not be able
to introduce a capability that nobody approved.
"""

from __future__ import annotations

import json

import pytest

from app.agent.llm import LLMResponse
from app.classification.taxonomy import Taxonomy, TaxonomyEntry
from tests.conftest import requires_db

TAXONOMY = Taxonomy([
    TaxonomyEntry("Authentication", "Login and identity", ("Login", "SSO", "MFA")),
    TaxonomyEntry("Scheduling", "Appointments", ("Rescheduling",)),
])


# --- taxonomy validation (no database) ------------------------------------


def test_approved_capability_is_accepted():
    cap, sub, reason = TAXONOMY.validate("Authentication", "SSO")
    assert (cap, sub, reason) == ("Authentication", "SSO", None)


def test_matching_is_case_insensitive_but_canonicalised():
    cap, sub, _ = TAXONOMY.validate("authentication", "sso")
    assert cap == "Authentication"
    assert sub == "SSO"


def test_invented_capability_is_rejected_not_created():
    cap, sub, reason = TAXONOMY.validate("Blockchain Integration")
    assert cap is None
    assert "not in the approved taxonomy" in reason


def test_invented_sub_capability_is_dropped_but_parent_kept():
    """The coarse label is still correct and still approved, so we keep it
    rather than throwing away a usable classification."""
    cap, sub, reason = TAXONOMY.validate("Authentication", "Biometrics")
    assert cap == "Authentication"
    assert sub is None
    assert reason is None


def test_sub_capability_from_a_different_parent_is_dropped():
    cap, sub, _ = TAXONOMY.validate("Scheduling", "SSO")
    assert cap == "Scheduling"
    assert sub is None


def test_abstention_is_honoured():
    cap, _, reason = TAXONOMY.validate("UNCLASSIFIED")
    assert cap is None
    assert "declined" in reason


def test_prompt_block_lists_only_approved_values():
    block = TAXONOMY.as_prompt_block()
    assert "Authentication" in block and "SSO" in block
    assert "Blockchain" not in block


# --- classifier behaviour --------------------------------------------------


def _llm_returning(payload: dict):
    class Stub:
        enabled = True

        def chat(self, *args, **kwargs):
            return LLMResponse(content=json.dumps(payload))

    return Stub()


@requires_db
def test_high_confidence_classification(session):
    from app.classification.classifier import CapabilityClassifier

    clf = CapabilityClassifier(
        session,
        llm=_llm_returning(
            {"capability": "Authentication", "sub_capability": "SSO", "confidence": 0.95}
        ),
    )
    result = clf.classify_work_item(1234)
    assert result.capability == "Authentication"
    assert result.confidence == 0.95
    assert result.is_low_confidence is False
    assert result.model_version == clf.settings.classifier_model_version


@requires_db
def test_low_confidence_is_flagged_not_hidden(session):
    from app.classification.classifier import CapabilityClassifier

    clf = CapabilityClassifier(
        session,
        llm=_llm_returning({"capability": "Scheduling", "confidence": 0.31}),
    )
    result = clf.classify_work_item(1234)
    assert result.is_low_confidence is True
    assert result.is_usable is True


@requires_db
def test_out_of_taxonomy_result_is_not_persistable(session):
    from app.classification.classifier import CapabilityClassifier

    clf = CapabilityClassifier(
        session,
        llm=_llm_returning({"capability": "Quantum Billing", "confidence": 0.99}),
    )
    result = clf.classify_work_item(1234)
    assert result.is_usable is False
    assert result.confidence == 0.0
    assert "not in the approved taxonomy" in result.rejected_reason


@requires_db
def test_abstention_when_the_model_declines(session):
    from app.classification.classifier import CapabilityClassifier

    clf = CapabilityClassifier(
        session, llm=_llm_returning({"capability": "UNCLASSIFIED", "confidence": 0.1})
    )
    result = clf.classify_work_item(1234)
    assert result.is_usable is False


@requires_db
def test_unknown_work_item_is_not_classified(session):
    from app.classification.classifier import CapabilityClassifier

    clf = CapabilityClassifier(session, llm=_llm_returning({"capability": "Authentication"}))
    result = clf.classify_work_item(424242)
    assert result.rejected_reason == "work item not found"


@requires_db
def test_malformed_confidence_is_clamped(session):
    from app.classification.classifier import CapabilityClassifier

    clf = CapabilityClassifier(
        session,
        llm=_llm_returning({"capability": "Authentication", "confidence": "very sure"}),
    )
    result = clf.classify_work_item(1234)
    assert result.confidence == 0.0


@requires_db
def test_llm_failure_does_not_produce_a_classification(session):
    from app.agent.llm import LLMError
    from app.classification.classifier import CapabilityClassifier

    class Broken:
        enabled = True

        def chat(self, *args, **kwargs):
            raise LLMError("upstream down")

    result = CapabilityClassifier(session, llm=Broken()).classify_work_item(1234)
    assert result.is_usable is False
    assert result.confidence == 0.0


def test_insufficient_signal_short_circuits():
    from app.classification.classifier import CapabilityClassifier

    has_signal = CapabilityClassifier._has_enough_signal
    assert has_signal({"title": "Implement single sign-on", "description": ""}, []) is True
    assert has_signal({"title": "fix", "description": ""}, []) is False
    assert has_signal({"title": "fix", "description": ""}, ["x" * 50]) is True
