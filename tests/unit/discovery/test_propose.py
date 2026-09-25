"""A proposal from the model becomes a Discovery Request only if it fits the Contract schema the engine runs: an unknown role, an unknown resolver or a capability that returns nothing is refused here."""

import pytest

from cua.discovery import ProposalError, spec_from_proposal
from tests.support.proposal import PROPOSAL, VENDOR


def test_a_proposal_becomes_a_discovery_request_in_the_engine_s_contract_shape():
    spec = spec_from_proposal(PROPOSAL, VENDOR)
    assert spec["role"] == "balance_reader"
    assert spec["contract"]["inputs"]["member_number"] == {
        "type": "string", "sensitive": True, "pattern": "^[0-9]{5}$"}
    assert spec["contract"]["outputs"] == {"savings_balance": {"type": "money", "sensitive": False}}
    assert spec["contract"]["outcomes"][0]["caller_hint"] == "Re-check the number."
    assert spec["example_values"] == {"member_number": "54321"}


def test_a_role_the_app_does_not_define_is_refused():
    with pytest.raises(ProposalError, match="not a Role"):
        spec_from_proposal(dict(PROPOSAL, role="superuser"), VENDOR)


def test_a_resolver_the_schema_does_not_know_is_refused():
    bad = dict(PROPOSAL, outcomes=[dict(PROPOSAL["outcomes"][0], resolver="the_model")])
    with pytest.raises(ProposalError, match="not a valid Contract"):
        spec_from_proposal(bad, VENDOR)


def test_a_capability_that_returns_nothing_is_refused():
    with pytest.raises(ProposalError, match="returns something"):
        spec_from_proposal(dict(PROPOSAL, outputs=[], outcomes=[]), VENDOR)
