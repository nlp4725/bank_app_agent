"""The Discovery Request from the command line: goal, Role, Contract, values.

No server and no model: these test that what a Reviewer types becomes the request
discovery receives, and that the shipped Contract did not move when it left the tool.
"""

import pytest

from tools._cli import load_dotenv
from tools.discovery.cli import CONTRACT, DEFAULT_CONTRACT, build, load_request, parse_args


def _request(*argv):
    return build(parse_args(list(argv)))


def test_the_default_request_is_the_sub_account_capability():
    r = _request()
    assert r.capability_id == "member.open_sub_account"
    assert r.role == "account_opener"
    assert r.contract == CONTRACT
    assert r.example_values["member_number"] == "54321"
    assert "member 54321" in r.goal


def test_a_bare_member_number_still_works_as_before():
    r = _request("99999")
    assert r.example_values["member_number"] == "99999"
    assert "member 99999" in r.goal


def test_a_goal_typed_on_the_command_line_reaches_the_model_with_its_values_filled():
    r = _request("--goal", "Look up member {member_number} and read the balance",
                 "--values", "member_number=12345")
    assert r.goal == "Look up member 12345 and read the balance"


def test_a_brace_the_values_do_not_name_is_left_as_written():
    r = _request("--goal", "Find {member_number} on {some_screen}")
    assert r.goal == "Find 54321 on {some_screen}"


def test_a_second_contract_file_changes_role_contract_and_capability_together():
    r = _request("--contract", "contracts/read_balance.yaml")
    assert r.role == "balance_reader"
    assert r.capability_id == "member.read_savings_balance"
    assert list(r.contract["outputs"]) == ["savings_balance"]
    assert "new_account_number" not in r.contract["outputs"]


def test_the_role_flag_overrides_the_file_but_the_contract_does_not_move():
    r = _request("--contract", "contracts/read_balance.yaml", "--role", "account_opener")
    assert r.role == "account_opener"
    assert r.contract == load_request("contracts/read_balance.yaml")["contract"]


def test_the_origin_comes_from_the_tenant_policy_not_from_a_flag():
    r = _request("--tenant", "bank_a")
    assert r.origin == "http://127.0.0.1:5001"
    with pytest.raises(SystemExit):        # there is no such flag, on purpose
        parse_args(["--origin", "http://evil.example"])


def test_the_exported_contract_is_the_file_so_record_and_review_compile_against_it():
    assert CONTRACT == load_request(DEFAULT_CONTRACT)["contract"]


def test_dotenv_fills_only_what_the_shell_did_not_set(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# key\nANTHROPIC_API_KEY='from-file'\nALREADY_SET=file\n\nbad line\n")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ALREADY_SET", "shell")
    assert load_dotenv(env) == ["ANTHROPIC_API_KEY"]
    import os
    assert os.environ["ANTHROPIC_API_KEY"] == "from-file"
    assert os.environ["ALREADY_SET"] == "shell"


def test_no_dotenv_file_is_not_an_error(tmp_path):
    assert load_dotenv(tmp_path / ".env") == []
