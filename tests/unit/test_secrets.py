"""Unit tests for secret obfuscation."""

from lib.database import _obfuscate_secrets


class TestObfuscateSecrets:
    """Test secret obfuscation patterns."""

    def test_password_flag_short(self):
        """Test -p flag obfuscation."""
        command = "mysql -u user -p MySecret123"
        result = _obfuscate_secrets(command)
        assert result == "mysql -u user -p ****"

    def test_password_flag_long(self):
        """Test --password flag obfuscation."""
        command = "psql --password MySecret123 -d mydb"
        result = _obfuscate_secrets(command)
        assert result == "psql --password **** -d mydb"

    def test_password_equals(self):
        """Test password= parameter obfuscation."""
        command = "connect password=MySecret123 host=localhost"
        result = _obfuscate_secrets(command)
        assert result == "connect password=**** host=localhost"

    def test_token_equals(self):
        """Test token= parameter obfuscation."""
        command = "api_call token=abc123xyz"
        result = _obfuscate_secrets(command)
        assert result == "api_call token=****"

    def test_api_key_equals(self):
        """Test api_key= parameter obfuscation with quotes in shell command."""
        command = "curl -H 'api_key=secret123'"
        result = _obfuscate_secrets(command)
        # The single quote closing the value is consumed by the pattern
        assert result == "curl -H 'api_key=****"

    def test_secret_equals(self):
        """Test secret= parameter obfuscation."""
        command = "deploy secret=mysecret app=myapp"
        result = _obfuscate_secrets(command)
        assert result == "deploy secret=**** app=myapp"

    def test_url_password(self):
        """Test password in URL obfuscation."""
        command = "git clone https://user:MyPassword@github.com/repo.git"
        result = _obfuscate_secrets(command)
        assert result == "git clone https://user:****@github.com/repo.git"

    def test_env_var_password(self):
        """Test environment variable password obfuscation."""
        command = "export NEO4J_PASSWORD=supersecret"
        result = _obfuscate_secrets(command)
        assert result == "export NEO4J_PASSWORD=****"

    def test_multiple_secrets(self):
        """Test multiple secrets in one command."""
        command = "deploy -p secret1 token=secret2 password=secret3"
        result = _obfuscate_secrets(command)
        assert result == "deploy -p **** token=**** password=****"

    def test_no_secrets(self):
        """Test command without secrets remains unchanged."""
        command = "ls -la /home/user"
        result = _obfuscate_secrets(command)
        assert result == "ls -la /home/user"

    def test_partial_match_not_obfuscated(self):
        """Test that partial matches aren't obfuscated incorrectly."""
        command = "use passport.js for auth"
        result = _obfuscate_secrets(command)
        # "passport" contains "pass" but shouldn't be obfuscated
        assert result == "use passport.js for auth"

    def test_quoted_password_with_spaces(self):
        """Test password in quotes with spaces is fully obfuscated."""
        command = 'mysql -p "My Secret 123"'
        result = _obfuscate_secrets(command)
        assert result == "mysql -p ****"

    def test_quoted_password_single_word(self):
        """Test password in single quotes without spaces."""
        command = "login --password 'MyPassword123'"
        result = _obfuscate_secrets(command)
        assert result == "login --password ****"

    def test_unquoted_password(self):
        """Test unquoted password is obfuscated."""
        command = "ssh -p MyPassword123 user@host"
        result = _obfuscate_secrets(command)
        assert result == "ssh -p **** user@host"
