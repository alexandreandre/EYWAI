from app.modules.badgeuse.domain.terminal_tokens import (
    generate_terminal_token,
    hash_terminal_token,
)


def test_generate_terminal_token_is_stable_hash():
    generated = generate_terminal_token()
    assert generated.raw_token
    assert generated.token_prefix == generated.raw_token[:8]
    assert hash_terminal_token(generated.raw_token) == generated.token_hash


def test_hash_terminal_token_trims_input():
    raw = "abc-def-token"
    assert hash_terminal_token(f"  {raw}  ") == hash_terminal_token(raw)
