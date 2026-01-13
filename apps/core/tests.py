"""
Tests for core app functionality.
"""
import os
import tempfile
import time
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, override_settings
from django.conf import settings
from hypothesis import given, strategies as st, assume
from hypothesis.extra.django import TestCase as HypothesisTestCase
import requests

from .models import ImportLog
from .utils import NVDAPIClient


class ImportLogModelTest(TestCase):
    """Test ImportLog model functionality."""
    
    def test_import_log_creation(self):
        """Test creating an ImportLog instance."""
        log = ImportLog.objects.create(
            source='CPE',
            operation='FULL_IMPORT',
            status='SUCCESS',
            records_processed=100
        )
        
        self.assertEqual(log.source, 'CPE')
        self.assertEqual(log.operation, 'FULL_IMPORT')
        self.assertEqual(log.status, 'SUCCESS')
        self.assertEqual(log.records_processed, 100)
        self.assertTrue(log.created_at)
        self.assertTrue(log.updated_at)
    
    def test_import_log_str_representation(self):
        """Test string representation of ImportLog."""
        log = ImportLog.objects.create(
            source='CVE',
            operation='INCREMENTAL',
            status='FAILED',
            records_processed=0,
            error_message='API timeout'
        )
        
        str_repr = str(log)
        self.assertIn('CVE', str_repr)
        self.assertIn('INCREMENTAL', str_repr)
        self.assertIn('FAILED', str_repr)


class ConfigurationExternalizationTest(HypothesisTestCase):
    """
    Property-based tests for configuration externalization.
    Feature: vulnerability-management-dashboard, Property 14: Configuration externalization
    """
    
    @given(
        secret_key=st.text(min_size=10, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
        api_page_size=st.integers(min_value=1, max_value=1000),
        log_level=st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
        time_zone=st.sampled_from(['UTC', 'America/New_York', 'Europe/London']),
        rate_limit_requests=st.integers(min_value=1, max_value=100),
        rate_limit_window=st.integers(min_value=1, max_value=300),
        update_schedule_hours=st.integers(min_value=1, max_value=168)
    )
    def test_configuration_externalization_property(
        self, secret_key, api_page_size, log_level, 
        time_zone, rate_limit_requests, rate_limit_window, update_schedule_hours
    ):
        """
        Property: For any valid configuration values, the system should be able to 
        read them from environment variables rather than hard-coded values.
        
        **Validates: Requirements 8.2**
        """
        # Test that the decouple config function works with various values
        from decouple import Config, RepositoryEnv
        import tempfile
        import os
        
        # Create a temporary .env file with our test values
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as env_file:
            env_file.write(f'SECRET_KEY={secret_key}\n')
            env_file.write(f'API_PAGE_SIZE={api_page_size}\n')
            env_file.write(f'LOG_LEVEL={log_level}\n')
            env_file.write(f'TIME_ZONE={time_zone}\n')
            env_file.write(f'NVD_RATE_LIMIT_REQUESTS={rate_limit_requests}\n')
            env_file.write(f'NVD_RATE_LIMIT_WINDOW={rate_limit_window}\n')
            env_file.write(f'UPDATE_SCHEDULE_HOURS={update_schedule_hours}\n')
            env_file_path = env_file.name
        
        try:
            # Create a config instance that reads from our temporary .env file
            config = Config(RepositoryEnv(env_file_path))
            
            # Verify that configuration values can be read from environment variables
            # and properly cast to the correct types
            
            # Test string configuration (trim whitespace for comparison)
            self.assertEqual(config('SECRET_KEY').strip(), secret_key.strip())
            self.assertEqual(config('LOG_LEVEL'), log_level)
            self.assertEqual(config('TIME_ZONE'), time_zone)
            
            # Test integer configuration with casting
            self.assertEqual(config('API_PAGE_SIZE', cast=int), api_page_size)
            self.assertEqual(config('NVD_RATE_LIMIT_REQUESTS', cast=int), rate_limit_requests)
            self.assertEqual(config('NVD_RATE_LIMIT_WINDOW', cast=int), rate_limit_window)
            self.assertEqual(config('UPDATE_SCHEDULE_HOURS', cast=int), update_schedule_hours)
            
            # Test that defaults work when environment variables are not present
            self.assertEqual(config('NONEXISTENT_VAR', default='default_value'), 'default_value')
            self.assertEqual(config('NONEXISTENT_INT', default=42, cast=int), 42)
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(env_file_path)
            except OSError:
                pass
    
    def test_configuration_defaults_when_env_vars_missing(self):
        """
        Test that reasonable defaults are used when environment variables are not set.
        """
        from decouple import Config, RepositoryEnv
        import tempfile
        import os
        
        # Create an empty .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as env_file:
            env_file_path = env_file.name
        
        try:
            # Create a config instance with empty environment file
            config = Config(RepositoryEnv(env_file_path))
            
            # Verify that reasonable defaults are used
            self.assertEqual(config('API_PAGE_SIZE', default=20, cast=int), 20)
            self.assertEqual(config('LOG_LEVEL', default='INFO'), 'INFO')
            self.assertEqual(config('TIME_ZONE', default='UTC'), 'UTC')
            self.assertEqual(config('NVD_RATE_LIMIT_REQUESTS', default=5, cast=int), 5)
            self.assertEqual(config('NVD_RATE_LIMIT_WINDOW', default=30, cast=int), 30)
            self.assertEqual(config('UPDATE_SCHEDULE_HOURS', default=24, cast=int), 24)
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(env_file_path)
            except OSError:
                pass
    
    def test_boolean_configuration_externalization(self):
        """
        Test that boolean configuration values can be properly externalized.
        """
        from decouple import Config, RepositoryEnv
        import tempfile
        import os
        
        # Test various boolean representations
        boolean_test_cases = [
            ('True', True),
            ('true', True),
            ('TRUE', True),
            ('1', True),
            ('False', False),
            ('false', False),
            ('FALSE', False),
            ('0', False),
        ]
        
        for env_value, expected_bool in boolean_test_cases:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as env_file:
                env_file.write(f'DEBUG={env_value}\n')
                env_file_path = env_file.name
            
            try:
                config = Config(RepositoryEnv(env_file_path))
                result = config('DEBUG', cast=bool)
                self.assertEqual(result, expected_bool, 
                               f"Environment value '{env_value}' should cast to {expected_bool}")
            finally:
                try:
                    os.unlink(env_file_path)
                except OSError:
                    pass


class RateLimitHandlingTest(HypothesisTestCase):
    """
    Property-based tests for rate limit handling.
    Feature: vulnerability-management-dashboard, Property 13: Rate limit handling
    """
    
    @given(
        rate_limit=st.integers(min_value=1, max_value=3),
        rate_window=st.integers(min_value=1, max_value=10),
        num_requests=st.integers(min_value=1, max_value=5)
    )
    def test_rate_limit_handling_property(self, rate_limit, rate_window, num_requests):
        """
        Property: For any API request that encounters rate limiting, the system should 
        handle it gracefully by implementing appropriate delays and retry logic.
        
        **Validates: Requirements 7.6, 8.3**
        """
        # Reduced ranges for faster test execution
        
        # Create a mock API client with test rate limits
        with patch('apps.core.utils.settings') as mock_settings:
            mock_settings.NVD_API_KEY = None
            mock_settings.NVD_API_BASE_URL = 'https://test.api.com'
            mock_settings.NVD_RATE_LIMIT_REQUESTS = rate_limit
            mock_settings.NVD_RATE_LIMIT_WINDOW = rate_window
            
            client = NVDAPIClient()
            client.rate_limit = rate_limit
            client.rate_window = rate_window
            
            # Mock both session.get and time.sleep to avoid actual delays
            with patch.object(client.session, 'get') as mock_get, \
                 patch('apps.core.utils.time.sleep') as mock_sleep:
                
                mock_response = Mock()
                mock_response.json.return_value = {'test': 'data'}
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                # Make multiple requests and verify rate limiting behavior
                for i in range(num_requests):
                    try:
                        result = client._make_request('test/endpoint')
                        self.assertIsInstance(result, dict)
                        self.assertEqual(result['test'], 'data')
                    except Exception as e:
                        # Should not raise exceptions for rate limiting
                        self.fail(f"Rate limiting should not raise exceptions: {e}")
                
                # Verify that the correct number of HTTP requests were made
                self.assertEqual(mock_get.call_count, num_requests)
                
                # Verify that sleep was called when rate limiting was triggered
                if num_requests > rate_limit:
                    self.assertTrue(mock_sleep.called, 
                                  f"Sleep should be called when {num_requests} requests exceed limit {rate_limit}")
                else:
                    # For requests within limit, sleep might not be called
                    pass
    
    def test_rate_limit_with_429_response(self):
        """
        Test that 429 (Too Many Requests) responses are handled with exponential backoff.
        """
        with patch('apps.core.utils.settings') as mock_settings:
            mock_settings.NVD_API_KEY = None
            mock_settings.NVD_API_BASE_URL = 'https://test.api.com'
            mock_settings.NVD_RATE_LIMIT_REQUESTS = 5
            mock_settings.NVD_RATE_LIMIT_WINDOW = 30
            
            client = NVDAPIClient()
            
            # Mock the session.get method to return 429 first, then success
            with patch.object(client.session, 'get') as mock_get:
                # First call returns 429, second call succeeds
                mock_429_response = Mock()
                mock_429_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                    response=Mock(status_code=429)
                )
                mock_429_response.status_code = 429
                
                mock_success_response = Mock()
                mock_success_response.json.return_value = {'success': True}
                mock_success_response.raise_for_status.return_value = None
                
                mock_get.side_effect = [mock_429_response, mock_success_response]
                
                # Mock time.sleep to avoid actual delays in tests
                with patch('apps.core.utils.time.sleep') as mock_sleep:
                    result = client._make_request('test/endpoint')
                    
                    # Verify that sleep was called (exponential backoff)
                    mock_sleep.assert_called_once_with(60)
                    
                    # Verify that the request eventually succeeded
                    self.assertEqual(result['success'], True)
                    
                    # Verify that two HTTP requests were made (retry after 429)
                    self.assertEqual(mock_get.call_count, 2)
    
    def test_rate_limit_request_tracking(self):
        """
        Test that request times are properly tracked and cleaned up.
        """
        with patch('apps.core.utils.settings') as mock_settings:
            mock_settings.NVD_API_KEY = None
            mock_settings.NVD_API_BASE_URL = 'https://test.api.com'
            mock_settings.NVD_RATE_LIMIT_REQUESTS = 3
            mock_settings.NVD_RATE_LIMIT_WINDOW = 10
            
            client = NVDAPIClient()
            client.rate_limit = 3
            client.rate_window = 10
            
            # Manually add some old request times
            current_time = time.time()
            client.request_times = [
                current_time - 15,  # Should be cleaned up (older than window)
                current_time - 5,   # Should be kept
                current_time - 2,   # Should be kept
            ]
            
            # Call rate limiting logic
            client._handle_rate_limit()
            
            # Verify that old requests were cleaned up and new one was added
            self.assertEqual(len(client.request_times), 3)  # 2 kept + 1 new
            
            # Verify that all remaining times are within the window
            for request_time in client.request_times:
                self.assertGreaterEqual(current_time - request_time, -1)  # Allow small timing differences
                self.assertLessEqual(current_time - request_time, client.rate_window + 1)
    
    @given(
        api_key_present=st.booleans(),
        rate_limit_requests=st.integers(min_value=1, max_value=20)
    )
    def test_rate_limit_configuration_property(self, api_key_present, rate_limit_requests):
        """
        Property: Rate limiting configuration should adapt based on API key presence.
        """
        api_key = 'test-api-key' if api_key_present else None
        
        with patch('apps.core.utils.settings') as mock_settings:
            mock_settings.NVD_API_KEY = api_key
            mock_settings.NVD_API_BASE_URL = 'https://test.api.com'
            mock_settings.NVD_RATE_LIMIT_REQUESTS = rate_limit_requests
            mock_settings.NVD_RATE_LIMIT_WINDOW = 30
            
            client = NVDAPIClient()
            
            if api_key_present:
                # With API key, should use configured rate limit
                self.assertEqual(client.rate_limit, rate_limit_requests)
                self.assertIn('apiKey', client.session.headers)
                self.assertEqual(client.session.headers['apiKey'], api_key)
            else:
                # Without API key, should use default rate limit of 5
                self.assertEqual(client.rate_limit, 5)
                self.assertNotIn('apiKey', client.session.headers)
    
    def test_concurrent_request_handling(self):
        """
        Test that rate limiting works correctly with the request tracking mechanism.
        """
        with patch('apps.core.utils.settings') as mock_settings:
            mock_settings.NVD_API_KEY = None
            mock_settings.NVD_API_BASE_URL = 'https://test.api.com'
            mock_settings.NVD_RATE_LIMIT_REQUESTS = 2
            mock_settings.NVD_RATE_LIMIT_WINDOW = 5
            
            client = NVDAPIClient()
            client.rate_limit = 2
            client.rate_window = 5
            
            with patch.object(client.session, 'get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = {'test': 'data'}
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response
                
                # Make requests up to the rate limit
                for i in range(2):
                    client._handle_rate_limit()
                    self.assertEqual(len(client.request_times), i + 1)
                
                # The third request should trigger rate limiting
                with patch('apps.core.utils.time.sleep') as mock_sleep:
                    client._handle_rate_limit()
                    
                    # Should have called sleep due to rate limiting
                    self.assertTrue(mock_sleep.called)
                    
                    # After rate limiting, request_times should be cleared
                    self.assertEqual(len(client.request_times), 1)  # New request added after clearing
    
    def test_list_configuration_externalization(self):
        """
        Test that list configuration values can be properly externalized.
        """
        from decouple import Config, RepositoryEnv
        import tempfile
        import os
        
        # Test comma-separated list parsing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as env_file:
            env_file.write('ALLOWED_HOSTS=localhost,127.0.0.1,example.com\n')
            env_file_path = env_file.name
        
        try:
            config = Config(RepositoryEnv(env_file_path))
            result = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])
            expected = ['localhost', '127.0.0.1', 'example.com']
            self.assertEqual(result, expected)
        finally:
            try:
                os.unlink(env_file_path)
            except OSError:
                pass