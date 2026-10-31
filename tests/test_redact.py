"""Tests for the Redaction engine (NFR-5, 20+ test cases)."""

from wraith.redact import redact


def test_redact_aws_access_key():
    cmd = "aws s3 cp file.txt s3://bucket/ --access-key AKIAIOSFODNN7EXAMPLE"
    assert "AKIAIOSFODNN7EXAMPLE" not in redact(cmd)
    assert "<redacted>" in redact(cmd)


def test_redact_jwt_token():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    cmd = f"curl -H 'Authorization: Bearer {jwt}' https://api.example.com"
    redacted = redact(cmd)
    assert jwt not in redacted
    assert "<redacted>" in redacted


def test_redact_url_with_credentials():
    cmd = "git clone https://alice:secretpass123@github.com/org/repo.git"
    redacted = redact(cmd)
    assert "secretpass123" not in redacted
    assert "https://<redacted>@github.com/org/repo.git" in redacted


def test_redact_postgres_url():
    cmd = "psql postgresql://postgres:mypassword@localhost:5432/mydb"
    redacted = redact(cmd)
    assert "mypassword" not in redacted
    assert "postgresql://<redacted>@localhost:5432/mydb" in redacted


def test_redact_cli_flag_password_equals():
    cmd = "mysql -u root --password=superSecret123 mydb"
    redacted = redact(cmd)
    assert "superSecret123" not in redacted
    assert "--password=<redacted>" in redacted


def test_redact_cli_flag_password_space():
    cmd = "mysql -u root --password myTopSecretPass"
    redacted = redact(cmd)
    assert "myTopSecretPass" not in redacted
    assert "--password <redacted>" in redacted


def test_redact_cli_flag_p_short():
    cmd = "mysql -u root -p secret456 db"
    redacted = redact(cmd)
    assert "secret456" not in redacted
    assert "-p <redacted>" in redacted


def test_redact_cli_flag_token():
    cmd = "npm publish --token=npm_998877665544332211"
    redacted = redact(cmd)
    assert "npm_998877665544332211" not in redacted
    assert "--token=<redacted>" in redacted


def test_redact_cli_flag_api_key():
    cmd = "app --api-key secret_api_key_12345 run"
    redacted = redact(cmd)
    assert "secret_api_key_12345" not in redacted
    assert "--api-key <redacted>" in redacted


def test_redact_env_var_token():
    cmd = "TOKEN=xoxb-1234567890-abcdef python bot.py"
    redacted = redact(cmd)
    assert "xoxb-1234567890-abcdef" not in redacted
    assert "TOKEN=<redacted>" in redacted


def test_redact_env_var_secret():
    cmd = "CLIENT_SECRET='very_confidential' ./server"
    redacted = redact(cmd)
    assert "very_confidential" not in redacted
    assert "CLIENT_SECRET=<redacted>" in redacted


def test_redact_env_var_auth():
    cmd = "AUTH_KEY=999988887777 ./start.sh"
    redacted = redact(cmd)
    assert "999988887777" not in redacted
    assert "AUTH_KEY=<redacted>" in redacted


def test_redact_github_pat():
    pat = "ghp_123456789012345678901234567890123456"
    cmd = f"curl -H 'Authorization: token {pat}' https://api.github.com"
    redacted = redact(cmd)
    assert pat not in redacted
    assert "<redacted>" in redacted


def test_redact_slack_token():
    token = "xoxb-1234567890-1234567890123-4567890123456"
    cmd = f"slack-cli --token {token}"
    redacted = redact(cmd)
    assert token not in redacted
    assert "<redacted>" in redacted


def test_redact_private_key_block():
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
    cmd = f"echo '{key}' > id_rsa"
    redacted = redact(cmd)
    assert "MIIEowIBAAKCAQEA0" not in redacted
    assert "<redacted>" in redacted


def test_redact_authorization_header():
    cmd = 'curl -H "Authorization: Bearer secret_bearer_token" https://api.local'
    redacted = redact(cmd)
    assert "secret_bearer_token" not in redacted
    assert "Authorization: <redacted>" in redacted or "<redacted>" in redacted


def test_redact_high_entropy_string():
    clean_entropy = "aB39zK1mP0vX8qW4yT7rE2uN6jH5gD8kLzXyWvUtSrQp"
    cmd = f"deploy --secret-payload {clean_entropy}"
    redacted = redact(cmd)
    assert clean_entropy not in redacted
    assert "<redacted>" in redacted


def test_redact_custom_pattern():
    cmd = "custom-tool --custom-val sensitiveXYZ"
    redacted = redact(cmd, custom_patterns=[r"sensitive[A-Z]+"])
    assert "sensitiveXYZ" not in redacted
    assert "<redacted>" in redacted


# False positive checks on normal commands:
def test_no_false_positive_git_commit():
    cmd = 'git commit -m "update pass condition in auth test"'
    redacted = redact(cmd)
    assert redacted == cmd


def test_no_false_positive_normal_flags():
    cmd = "python -m pytest tests/ -v -k test_auth"
    redacted = redact(cmd)
    assert redacted == cmd


def test_no_false_positive_rm_rf():
    cmd = "rm -rf build node_modules"
    redacted = redact(cmd)
    assert redacted == cmd


def test_no_false_positive_curl_plain():
    cmd = "curl -X GET https://example.com/api/v1/users"
    redacted = redact(cmd)
    assert redacted == cmd
