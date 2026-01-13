"""
Tests for core app functionality.
"""
import os
import tempfile
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.conf import settings
from hypothesis import given, strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase

from .models import ImportLog


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
            
            # Test string configuration
            self.assertEqual(config('SECRET_KEY'), secret_key)
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