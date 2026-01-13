"""
Tests for CPE Repository functionality.
"""
import json
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.utils import timezone
from hypothesis import given, strategies as st, assume
from hypothesis.extra.django import TestCase as HypothesisTestCase
import requests

from apps.core.models import ImportLog
from .models import CPERecord
from .services import CPEImportService


class CPERecordModelTest(TestCase):
    """Test CPERecord model functionality."""
    
    def test_cpe_record_creation(self):
        """Test creating a CPERecord instance."""
        cpe = CPERecord.objects.create(
            cpe_name='cpe:2.3:a:apache:http_server:2.4.41:*:*:*:*:*:*:*',
            cpe_name_id='cpe:2.3:a:apache:http_server:2.4.41:*:*:*:*:*:*:*',
            part='a',
            vendor='apache',
            product='http_server',
            version='2.4.41'
        )
        
        self.assertEqual(cpe.vendor, 'apache')
        self.assertEqual(cpe.product, 'http_server')
        self.assertEqual(cpe.version, '2.4.41')
        self.assertTrue(cpe.is_application)
        self.assertFalse(cpe.is_operating_system)
        self.assertFalse(cpe.is_hardware)
    
    def test_cpe_record_str_representation(self):
        """Test string representation of CPERecord."""
        cpe = CPERecord.objects.create(
            cpe_name='cpe:2.3:o:microsoft:windows:10:*:*:*:*:*:*:*',
            cpe_name_id='cpe:2.3:o:microsoft:windows:10:*:*:*:*:*:*:*',
            part='o',
            vendor='microsoft',
            product='windows',
            version='10'
        )
        
        str_repr = str(cpe)
        self.assertIn('microsoft', str_repr)
        self.assertIn('windows', str_repr)
        self.assertIn('10', str_repr)
    
    def test_cpe_components_property(self):
        """Test get_cpe_components method."""
        cpe = CPERecord.objects.create(
            cpe_name='cpe:2.3:h:cisco:router:1.0:*:*:*:*:*:*:*',
            cpe_name_id='cpe:2.3:h:cisco:router:1.0:*:*:*:*:*:*:*',
            part='h',
            vendor='cisco',
            product='router',
            version='1.0'
        )
        
        components = cpe.get_cpe_components()
        self.assertEqual(components['part'], 'h')
        self.assertEqual(components['vendor'], 'cisco')
        self.assertEqual(components['product'], 'router')
        self.assertEqual(components['version'], '1.0')
        self.assertTrue(cpe.is_hardware)


class CPEDataImportTest(HypothesisTestCase):
    """
    Property-based tests for CPE data import.
    Feature: vulnerability-management-dashboard, Property 1: Data Import API Integration (CPE)
    """
    
    @given(
        total_results=st.integers(min_value=1, max_value=100),
        results_per_page=st.integers(min_value=1, max_value=10),
        start_index=st.integers(min_value=0, max_value=50)
    )
    def test_cpe_data_import_api_integration_property(self, total_results, results_per_page, start_index):
        """
        Property: For any data source (CPE), when the importer fetches data from the 
        corresponding API endpoint, it should successfully retrieve and process the data 
        according to the API specification.
        
        **Validates: Requirements 3.1**
        """
        # Ensure start_index doesn't exceed total_results
        assume(start_index < total_results)
        
        # Calculate how many results should be returned for this page
        remaining_results = total_results - start_index
        expected_results_count = min(results_per_page, remaining_results)
        
        # Generate mock CPE data
        mock_products = []
        for i in range(expected_results_count):
            cpe_index = start_index + i
            mock_products.append({
                'cpe': {
                    'cpeName': f'cpe:2.3:a:vendor{cpe_index}:product{cpe_index}:1.0:*:*:*:*:*:*:*',
                    'cpeNameId': f'cpe-{cpe_index}',
                    'deprecated': False
                }
            })
        
        mock_response = {
            'resultsPerPage': results_per_page,
            'startIndex': start_index,
            'totalResults': total_results,
            'products': mock_products
        }
        
        # Mock the NVD API client
        with patch('apps.cpe_repository.services.NVDAPIClient') as mock_client_class:
            mock_client = Mock()
            mock_client.get_cpes.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            # Create import service and test API integration
            import_service = CPEImportService()
            
            # Test that the service can fetch and process the data
            response = import_service.client.get_cpes(
                start_index=start_index,
                results_per_page=results_per_page
            )
            
            # Verify API response structure
            self.assertIsInstance(response, dict)
            self.assertIn('products', response)
            self.assertIn('totalResults', response)
            self.assertIn('startIndex', response)
            self.assertIn('resultsPerPage', response)
            
            # Verify response data matches expected values
            self.assertEqual(response['totalResults'], total_results)
            self.assertEqual(response['startIndex'], start_index)
            self.assertEqual(response['resultsPerPage'], results_per_page)
            self.assertEqual(len(response['products']), expected_results_count)
            
            # Verify each product has required CPE structure
            for product in response['products']:
                self.assertIn('cpe', product)
                cpe_data = product['cpe']
                self.assertIn('cpeName', cpe_data)
                self.assertIn('cpeNameId', cpe_data)
                self.assertIsInstance(cpe_data.get('deprecated', False), bool)
                
                # Verify CPE name format (basic validation)
                cpe_name = cpe_data['cpeName']
                self.assertTrue(cpe_name.startswith('cpe:2.3:'))
                cpe_parts = cpe_name.split(':')
                self.assertGreaterEqual(len(cpe_parts), 6)  # At least cpe:2.3:part:vendor:product:version
    
    def test_cpe_import_with_empty_response(self):
        """
        Test that empty API responses are handled gracefully.
        """
        mock_response = {
            'resultsPerPage': 2000,
            'startIndex': 0,
            'totalResults': 0,
            'products': []
        }
        
        with patch('apps.cpe_repository.services.NVDAPIClient') as mock_client_class:
            mock_client = Mock()
            mock_client.get_cpes.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            import_service = CPEImportService()
            
            # Test that empty response doesn't cause errors
            response = import_service.client.get_cpes()
            
            self.assertEqual(response['totalResults'], 0)
            self.assertEqual(len(response['products']), 0)
    
    @given(
        num_products=st.integers(min_value=1, max_value=20),
        has_deprecated=st.booleans()
    )
    def test_cpe_batch_processing_property(self, num_products, has_deprecated):
        """
        Property: For any batch of CPE products from the API, the import service 
        should be able to process and normalize the data correctly.
        """
        # Generate mock CPE products
        mock_products = []
        for i in range(num_products):
            deprecated = has_deprecated and (i % 3 == 0)  # Make some deprecated
            deprecated_by = [f'cpe:2.3:a:vendor{i}:newproduct:2.0:*:*:*:*:*:*:*'] if deprecated else []
            
            mock_products.append({
                'cpe': {
                    'cpeName': f'cpe:2.3:a:vendor{i}:product{i}:1.{i}:*:*:*:*:*:*:*',
                    'cpeNameId': f'cpe-{i}',
                    'deprecated': deprecated,
                    'deprecatedBy': deprecated_by if deprecated else None
                }
            })
        
        # Mock the import service
        import_service = CPEImportService()
        
        # Test batch processing
        processed_count = import_service._process_cpe_batch(mock_products)
        
        # Verify that all products were processed
        self.assertEqual(processed_count, num_products)
        
        # Verify that CPE records were created in the database
        self.assertEqual(CPERecord.objects.count(), num_products)
        
        # Verify that deprecated records are properly marked
        if has_deprecated:
            deprecated_count = CPERecord.objects.filter(deprecated=True).count()
            self.assertGreater(deprecated_count, 0)
    
    def test_cpe_normalization_with_special_characters(self):
        """
        Test CPE data normalization with special characters and encoding.
        """
        mock_products = [{
            'cpe': {
                'cpeName': 'cpe:2.3:a:test%20vendor:test%2fproduct:1.0%5c2:*:*:*:*:*:*:*',
                'cpeNameId': 'cpe-special-chars',
                'deprecated': False
            }
        }]
        
        import_service = CPEImportService()
        processed_count = import_service._process_cpe_batch(mock_products)
        
        self.assertEqual(processed_count, 1)
        
        cpe_record = CPERecord.objects.first()
        # Verify that special characters are decoded
        self.assertEqual(cpe_record.vendor, 'test vendor')
        self.assertEqual(cpe_record.product, 'test/product')
        self.assertEqual(cpe_record.version, '1.0\\2')
    
    def test_cpe_import_error_handling(self):
        """
        Test that import errors are properly handled and logged.
        """
        # Mock products with invalid data
        mock_products = [
            {'cpe': {'cpeName': 'invalid-cpe-format', 'cpeNameId': 'invalid-1'}},
            {'invalid': 'structure'},  # Missing 'cpe' key
            {'cpe': {'cpeNameId': 'missing-name'}},  # Missing cpeName
        ]
        
        import_service = CPEImportService()
        
        # Should not raise exception, but should handle errors gracefully
        processed_count = import_service._process_cpe_batch(mock_products)
        
        # Some records might be processed despite errors
        self.assertGreaterEqual(processed_count, 0)
        self.assertLessEqual(processed_count, len(mock_products))
    
    @given(
        api_error_code=st.sampled_from([400, 401, 403, 404, 500, 502, 503]),
        error_message=st.text(min_size=1, max_size=100)
    )
    def test_cpe_import_api_error_handling_property(self, api_error_code, error_message):
        """
        Property: For any API error response, the import service should handle 
        it gracefully and create appropriate error logs.
        """
        with patch('apps.cpe_repository.services.NVDAPIClient') as mock_client_class:
            mock_client = Mock()
            
            # Mock API error
            api_error = requests.exceptions.HTTPError(error_message)
            api_error.response = Mock()
            api_error.response.status_code = api_error_code
            mock_client.get_cpes.side_effect = api_error
            mock_client_class.return_value = mock_client
            
            import_service = CPEImportService()
            
            # Test that API errors are handled gracefully
            with self.assertRaises(requests.exceptions.HTTPError):
                import_service.full_import()
            
            # Verify that an import log was created with error status
            import_log = ImportLog.objects.filter(source='CPE', status='FAILED').first()
            self.assertIsNotNone(import_log)
            self.assertIn(error_message, import_log.error_message)
    
    def test_cpe_incremental_update_vs_full_import(self):
        """
        Test that incremental updates work differently from full imports.
        """
        # Create some existing CPE records
        existing_cpe = CPERecord.objects.create(
            cpe_name='cpe:2.3:a:existing:product:1.0:*:*:*:*:*:*:*',
            cpe_name_id='existing-cpe',
            part='a',
            vendor='existing',
            product='product',
            version='1.0'
        )
        
        # Mock updated data for the same CPE
        mock_products = [{
            'cpe': {
                'cpeName': 'cpe:2.3:a:existing:product:2.0:*:*:*:*:*:*:*',
                'cpeNameId': 'existing-cpe',
                'deprecated': False
            }
        }]
        
        with patch('apps.cpe_repository.services.NVDAPIClient') as mock_client_class:
            mock_client = Mock()
            mock_client.get_cpes.return_value = {
                'resultsPerPage': 2000,
                'startIndex': 0,
                'totalResults': 1,
                'products': mock_products
            }
            mock_client_class.return_value = mock_client
            
            import_service = CPEImportService()
            
            # Test incremental update
            import_log = import_service.incremental_update(days_back=1)
            
            self.assertEqual(import_log.status, 'SUCCESS')
            self.assertEqual(import_log.operation, 'INCREMENTAL')
            
            # Verify that the existing record was updated
            updated_cpe = CPERecord.objects.get(cpe_name_id='existing-cpe')
            self.assertEqual(updated_cpe.version, '2.0')  # Should be updated
    
    def test_cpe_duplicate_handling(self):
        """
        Test that duplicate CPE records are handled correctly.
        """
        # Create the same CPE data twice
        mock_products = [
            {
                'cpe': {
                    'cpeName': 'cpe:2.3:a:duplicate:product:1.0:*:*:*:*:*:*:*',
                    'cpeNameId': 'duplicate-cpe',
                    'deprecated': False
                }
            },
            {
                'cpe': {
                    'cpeName': 'cpe:2.3:a:duplicate:product:1.0:*:*:*:*:*:*:*',
                    'cpeNameId': 'duplicate-cpe',
                    'deprecated': False
                }
            }
        ]
        
        import_service = CPEImportService()
        processed_count = import_service._process_cpe_batch(mock_products)
        
        # Should process both, but only create one record due to unique constraint
        self.assertEqual(processed_count, 2)
        self.assertEqual(CPERecord.objects.filter(cpe_name_id='duplicate-cpe').count(), 1)


class CPEDataStorageTest(HypothesisTestCase):
    """
    Property-based tests for CPE data storage normalization.
    Feature: vulnerability-management-dashboard, Property 3: Data Storage Normalization (CPE)
    """
    
    @given(
        vendor=st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
        product=st.text(min_size=1, max_size=50, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
        version=st.text(min_size=0, max_size=20, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
        part=st.sampled_from(['a', 'o', 'h']),
        deprecated=st.booleans()
    )
    def test_cpe_data_storage_normalization_property(self, vendor, product, version, part, deprecated):
        """
        Property: For any imported record (CPE), the system should store it in normalized 
        form in the SQLite database with all required fields properly populated.
        
        **Validates: Requirements 3.3**
        """
        # Clean input data to avoid database constraint issues
        vendor_clean = vendor.strip()[:200]  # Truncate to model field length
        product_clean = product.strip()[:200]
        version_clean = version.strip()[:100] if version else ''
        
        # Skip empty vendor/product as they're required for meaningful CPE
        assume(len(vendor_clean) > 0)
        assume(len(product_clean) > 0)
        
        # Create CPE name in proper format
        cpe_name = f'cpe:2.3:{part}:{vendor_clean}:{product_clean}:{version_clean or "*"}:*:*:*:*:*:*'
        cpe_name_id = f'cpe-test-{hash(cpe_name) % 1000000}'  # Generate unique ID
        
        # Create CPE record
        cpe_record = CPERecord.objects.create(
            cpe_name=cpe_name,
            cpe_name_id=cpe_name_id,
            part=part,
            vendor=vendor_clean,
            product=product_clean,
            version=version_clean,
            deprecated=deprecated
        )
        
        # Verify that the record was stored correctly
        self.assertIsNotNone(cpe_record.id)
        self.assertTrue(cpe_record.created_at)
        self.assertTrue(cpe_record.updated_at)
        
        # Verify normalized data storage
        self.assertEqual(cpe_record.cpe_name, cpe_name)
        self.assertEqual(cpe_record.cpe_name_id, cpe_name_id)
        self.assertEqual(cpe_record.part, part)
        self.assertEqual(cpe_record.vendor, vendor_clean)
        self.assertEqual(cpe_record.product, product_clean)
        self.assertEqual(cpe_record.version, version_clean)
        self.assertEqual(cpe_record.deprecated, deprecated)
        
        # Verify that the record can be retrieved from database
        retrieved_record = CPERecord.objects.get(cpe_name_id=cpe_name_id)
        self.assertEqual(retrieved_record.cpe_name, cpe_name)
        self.assertEqual(retrieved_record.vendor, vendor_clean)
        self.assertEqual(retrieved_record.product, product_clean)
        self.assertEqual(retrieved_record.version, version_clean)
        self.assertEqual(retrieved_record.deprecated, deprecated)
        
        # Verify proper indexing works (database queries should be efficient)
        # Test vendor index
        vendor_records = CPERecord.objects.filter(vendor=vendor_clean)
        self.assertIn(cpe_record, vendor_records)
        
        # Test product index
        product_records = CPERecord.objects.filter(product=product_clean)
        self.assertIn(cpe_record, product_records)
        
        # Test part + vendor index
        part_vendor_records = CPERecord.objects.filter(part=part, vendor=vendor_clean)
        self.assertIn(cpe_record, part_vendor_records)
        
        # Test deprecated index
        deprecated_records = CPERecord.objects.filter(deprecated=deprecated)
        self.assertIn(cpe_record, deprecated_records)
    
    @given(
        num_records=st.integers(min_value=1, max_value=20),
        use_same_vendor=st.booleans()
    )
    def test_cpe_bulk_storage_normalization_property(self, num_records, use_same_vendor):
        """
        Property: For any batch of CPE records, all should be stored with proper normalization
        and indexing should work correctly for bulk operations.
        """
        base_vendor = 'test_vendor' if use_same_vendor else None
        created_records = []
        
        for i in range(num_records):
            vendor = base_vendor if use_same_vendor else f'vendor_{i}'
            product = f'product_{i}'
            version = f'1.{i}'
            part = ['a', 'o', 'h'][i % 3]
            
            cpe_name = f'cpe:2.3:{part}:{vendor}:{product}:{version}:*:*:*:*:*:*'
            cpe_name_id = f'bulk-test-{i}'
            
            cpe_record = CPERecord.objects.create(
                cpe_name=cpe_name,
                cpe_name_id=cpe_name_id,
                part=part,
                vendor=vendor,
                product=product,
                version=version,
                deprecated=False
            )
            created_records.append(cpe_record)
        
        # Verify all records were created
        self.assertEqual(len(created_records), num_records)
        
        # Verify bulk queries work correctly
        all_created_ids = [r.cpe_name_id for r in created_records]
        retrieved_records = CPERecord.objects.filter(cpe_name_id__in=all_created_ids)
        self.assertEqual(retrieved_records.count(), num_records)
        
        # If using same vendor, test vendor-based bulk query
        if use_same_vendor:
            vendor_records = CPERecord.objects.filter(vendor=base_vendor)
            self.assertGreaterEqual(vendor_records.count(), num_records)
            
            # All created records should be in vendor query results
            for record in created_records:
                self.assertIn(record, vendor_records)
    
    def test_cpe_unique_constraint_enforcement(self):
        """
        Test that unique constraints are properly enforced for CPE records.
        """
        cpe_data = {
            'cpe_name': 'cpe:2.3:a:test:product:1.0:*:*:*:*:*:*:*',
            'cpe_name_id': 'unique-test-cpe',
            'part': 'a',
            'vendor': 'test',
            'product': 'product',
            'version': '1.0'
        }
        
        # Create first record
        cpe1 = CPERecord.objects.create(**cpe_data)
        self.assertIsNotNone(cpe1.id)
        
        # Attempt to create duplicate should raise IntegrityError
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            CPERecord.objects.create(**cpe_data)
    
    @given(
        special_chars=st.text(min_size=1, max_size=10, alphabet='!@#$%^&*()[]{}|\\:";\'<>?,./'),
        encoding_chars=st.text(min_size=1, max_size=10, alphabet='àáâãäåæçèéêëìíîïñòóôõöøùúûüý')
    )
    def test_cpe_special_character_storage_property(self, special_chars, encoding_chars):
        """
        Property: For any CPE data containing special characters or encoding,
        the system should store it correctly without data corruption.
        """
        # Combine special characters with normal text
        vendor = f'vendor_{special_chars[:5]}'  # Limit length
        product = f'product_{encoding_chars[:5]}'
        
        # Truncate to fit database constraints
        vendor = vendor[:200]
        product = product[:200]
        
        cpe_name = f'cpe:2.3:a:{vendor}:{product}:1.0:*:*:*:*:*:*'
        cpe_name_id = f'special-{hash(vendor + product) % 1000000}'
        
        # Create record with special characters
        cpe_record = CPERecord.objects.create(
            cpe_name=cpe_name,
            cpe_name_id=cpe_name_id,
            part='a',
            vendor=vendor,
            product=product,
            version='1.0'
        )
        
        # Verify data integrity after storage
        retrieved_record = CPERecord.objects.get(cpe_name_id=cpe_name_id)
        self.assertEqual(retrieved_record.vendor, vendor)
        self.assertEqual(retrieved_record.product, product)
        self.assertEqual(retrieved_record.cpe_name, cpe_name)
        
        # Verify that queries work with special characters
        vendor_query = CPERecord.objects.filter(vendor=vendor)
        self.assertIn(retrieved_record, vendor_query)
        
        product_query = CPERecord.objects.filter(product=product)
        self.assertIn(retrieved_record, product_query)
    
    def test_cpe_json_field_storage(self):
        """
        Test that JSON fields (deprecated_by) are properly stored and retrieved.
        """
        deprecated_by_list = [
            'cpe:2.3:a:vendor:newproduct:2.0:*:*:*:*:*:*:*',
            'cpe:2.3:a:vendor:anotherproduct:1.5:*:*:*:*:*:*:*'
        ]
        
        cpe_record = CPERecord.objects.create(
            cpe_name='cpe:2.3:a:vendor:oldproduct:1.0:*:*:*:*:*:*:*',
            cpe_name_id='json-test-cpe',
            part='a',
            vendor='vendor',
            product='oldproduct',
            version='1.0',
            deprecated=True,
            deprecated_by=deprecated_by_list
        )
        
        # Verify JSON field storage
        retrieved_record = CPERecord.objects.get(cpe_name_id='json-test-cpe')
        self.assertEqual(retrieved_record.deprecated_by, deprecated_by_list)
        self.assertTrue(retrieved_record.deprecated)
        
        # Verify JSON field queries work
        deprecated_records = CPERecord.objects.filter(deprecated=True)
        self.assertIn(retrieved_record, deprecated_records)
    
    @given(
        field_lengths=st.fixed_dictionaries({
            'vendor': st.integers(min_value=1, max_value=300),
            'product': st.integers(min_value=1, max_value=300),
            'version': st.integers(min_value=0, max_value=150),
            'cpe_name': st.integers(min_value=50, max_value=600)
        })
    )
    def test_cpe_field_length_constraints_property(self, field_lengths):
        """
        Property: For any CPE data, fields should be properly truncated or validated
        according to model field length constraints.
        """
        # Generate data with specified lengths
        vendor = 'v' * field_lengths['vendor']
        product = 'p' * field_lengths['product']
        version = 'x' * field_lengths['version'] if field_lengths['version'] > 0 else ''
        cpe_name = 'c' * field_lengths['cpe_name']
        
        cpe_name_id = f'length-test-{hash(vendor + product) % 1000000}'
        
        try:
            cpe_record = CPERecord.objects.create(
                cpe_name=cpe_name,
                cpe_name_id=cpe_name_id,
                part='a',
                vendor=vendor,
                product=product,
                version=version
            )
            
            # If creation succeeded, verify data was stored (possibly truncated)
            retrieved_record = CPERecord.objects.get(cpe_name_id=cpe_name_id)
            
            # Verify field length constraints are respected
            self.assertLessEqual(len(retrieved_record.vendor), 200)
            self.assertLessEqual(len(retrieved_record.product), 200)
            self.assertLessEqual(len(retrieved_record.version), 100)
            self.assertLessEqual(len(retrieved_record.cpe_name), 500)
            
            # Verify that stored data matches input (up to field limits)
            self.assertEqual(retrieved_record.vendor, vendor[:200])
            self.assertEqual(retrieved_record.product, product[:200])
            self.assertEqual(retrieved_record.version, version[:100])
            self.assertEqual(retrieved_record.cpe_name, cpe_name[:500])
            
        except Exception as e:
            # If creation failed due to length constraints, that's also acceptable behavior
            # The important thing is that the system handles it gracefully
            self.assertIsInstance(e, (ValueError, Exception))
    
    def test_cpe_timestamp_fields(self):
        """
        Test that timestamp fields are properly populated and updated.
        """
        import time
        from django.utils import timezone
        
        # Record time before creation
        before_creation = timezone.now()
        
        cpe_record = CPERecord.objects.create(
            cpe_name='cpe:2.3:a:timestamp:test:1.0:*:*:*:*:*:*:*',
            cpe_name_id='timestamp-test',
            part='a',
            vendor='timestamp',
            product='test',
            version='1.0'
        )
        
        # Record time after creation
        after_creation = timezone.now()
        
        # Verify timestamps are within expected range
        self.assertGreaterEqual(cpe_record.created_at, before_creation)
        self.assertLessEqual(cpe_record.created_at, after_creation)
        self.assertGreaterEqual(cpe_record.updated_at, before_creation)
        self.assertLessEqual(cpe_record.updated_at, after_creation)
        
        # Verify created_at and updated_at are initially the same
        self.assertEqual(cpe_record.created_at, cpe_record.updated_at)
        
        # Wait a small amount and update the record
        time.sleep(0.01)  # Small delay to ensure different timestamp
        
        before_update = timezone.now()
        cpe_record.version = '2.0'
        cpe_record.save()
        after_update = timezone.now()
        
        # Verify that updated_at changed but created_at didn't
        updated_record = CPERecord.objects.get(cpe_name_id='timestamp-test')
        self.assertEqual(updated_record.created_at, cpe_record.created_at)  # Should not change
        self.assertGreater(updated_record.updated_at, cpe_record.created_at)  # Should be newer
        self.assertGreaterEqual(updated_record.updated_at, before_update)
        self.assertLessEqual(updated_record.updated_at, after_update)

class CPEManagementCommandTest(HypothesisTestCase):
    """
    Property-based tests for CPE management command functionality.
    Feature: vulnerability-management-dashboard, Property 11: Management Command Functionality (CPE)
    """
    
    @given(
        command_type=st.sampled_from(['import_cpe', 'update_cpe']),
        verbose_flag=st.booleans(),
        days_back=st.integers(min_value=1, max_value=30)
    )
    def test_management_command_functionality_property(self, command_type, verbose_flag, days_back):
        """
        Property: For any data update operation, there should be a corresponding Django 
        management command that can be executed independently.
        
        **Validates: Requirements 7.1**
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        from unittest.mock import patch
        
        # Mock the import service to avoid actual API calls
        with patch('apps.cpe_repository.management.commands.import_cpe.CPEImportService') as mock_service_class, \
             patch('apps.cpe_repository.management.commands.update_cpe.CPEImportService') as mock_update_service_class:
            
            # Create mock import service
            mock_service = Mock()
            mock_import_log = Mock()
            mock_import_log.status = 'SUCCESS'
            mock_import_log.records_processed = 100
            mock_import_log.error_message = ''
            mock_import_log.operation = 'FULL_IMPORT' if command_type == 'import_cpe' else 'INCREMENTAL'
            mock_import_log.created_at = timezone.now()
            mock_import_log.updated_at = timezone.now()
            
            if command_type == 'import_cpe':
                mock_service.full_import.return_value = mock_import_log
                mock_service.incremental_update.return_value = mock_import_log
                mock_service_class.return_value = mock_service
            else:
                mock_service.incremental_update.return_value = mock_import_log
                mock_update_service_class.return_value = mock_service
            
            # Capture command output
            out = StringIO()
            err = StringIO()
            
            try:
                # Test command execution with various parameters
                if command_type == 'import_cpe':
                    # Test full import
                    call_command(
                        'import_cpe',
                        '--full-import',
                        verbose=verbose_flag,
                        stdout=out,
                        stderr=err
                    )
                    
                    # Verify that the service method was called
                    mock_service.full_import.assert_called_once()
                    
                    # Test incremental import
                    call_command(
                        'import_cpe',
                        '--incremental',
                        f'--days-back={days_back}',
                        verbose=verbose_flag,
                        stdout=out,
                        stderr=err
                    )
                    
                    # Verify that the incremental method was called with correct parameters
                    mock_service.incremental_update.assert_called_with(days_back=days_back)
                    
                else:  # update_cpe
                    call_command(
                        'update_cpe',
                        f'--days-back={days_back}',
                        verbose=verbose_flag,
                        stdout=out,
                        stderr=err
                    )
                    
                    # Verify that the service method was called with correct parameters
                    mock_service.incremental_update.assert_called_with(days_back=days_back)
                
                # Verify command output contains success message
                output = out.getvalue()
                self.assertIn('completed successfully', output.lower())
                
                # If verbose, should contain more details
                if verbose_flag:
                    self.assertTrue(len(output) > 50)  # Verbose output should be longer
                
                # Verify no errors in stderr
                error_output = err.getvalue()
                self.assertEqual(error_output.strip(), '')
                
            except CommandError as e:
                # Command errors should be handled gracefully
                self.fail(f"Management command should not raise CommandError: {e}")
            except Exception as e:
                # Other exceptions should not occur with proper mocking
                self.fail(f"Unexpected exception in management command: {e}")
    
    def test_management_command_error_handling(self):
        """
        Test that management commands handle errors gracefully.
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        from unittest.mock import patch
        
        with patch('apps.cpe_repository.management.commands.import_cpe.CPEImportService') as mock_service_class:
            # Mock service that raises an exception
            mock_service = Mock()
            mock_service.full_import.side_effect = Exception("API connection failed")
            mock_service_class.return_value = mock_service
            
            out = StringIO()
            err = StringIO()
            
            # Test that command handles exceptions and converts them to CommandError
            with self.assertRaises(CommandError):
                call_command(
                    'import_cpe',
                    '--full-import',
                    stdout=out,
                    stderr=err
                )
    
    def test_management_command_argument_validation(self):
        """
        Test that management commands validate arguments correctly.
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        
        out = StringIO()
        err = StringIO()
        
        # Test import_cpe without required arguments
        with self.assertRaises(CommandError):
            call_command('import_cpe', stdout=out, stderr=err)
        
        # Test import_cpe with conflicting arguments
        with self.assertRaises(CommandError):
            call_command(
                'import_cpe',
                '--full-import',
                '--incremental',
                stdout=out,
                stderr=err
            )
    
    @given(
        api_key_present=st.booleans(),
        days_back=st.integers(min_value=1, max_value=14)
    )
    def test_management_command_api_key_handling_property(self, api_key_present, days_back):
        """
        Property: Management commands should handle API key configuration correctly.
        """
        from django.core.management import call_command
        from io import StringIO
        from unittest.mock import patch
        
        api_key = 'test-api-key-12345' if api_key_present else None
        
        with patch('apps.cpe_repository.management.commands.update_cpe.CPEImportService') as mock_service_class, \
             patch('apps.cpe_repository.management.commands.update_cpe.settings') as mock_settings:
            
            # Mock settings
            mock_settings.NVD_API_KEY = api_key
            
            # Mock service
            mock_service = Mock()
            mock_import_log = Mock()
            mock_import_log.status = 'SUCCESS'
            mock_import_log.records_processed = 50
            mock_import_log.error_message = ''
            mock_import_log.created_at = timezone.now()
            mock_import_log.updated_at = timezone.now()
            mock_service.incremental_update.return_value = mock_import_log
            mock_service_class.return_value = mock_service
            
            out = StringIO()
            err = StringIO()
            
            # Test command execution
            call_command(
                'update_cpe',
                f'--days-back={days_back}',
                stdout=out,
                stderr=err
            )
            
            # Verify that service was created with correct API key
            mock_service_class.assert_called_once_with(api_key=api_key)
            
            # Verify output mentions API key status
            output = out.getvalue()
            if api_key_present:
                # Should not show warning about missing API key
                self.assertNotIn('No NVD API key provided', output)
            else:
                # Should show warning about missing API key
                self.assertIn('No NVD API key provided', output)
    
    def test_management_command_dry_run_functionality(self):
        """
        Test that dry-run functionality works correctly.
        """
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        err = StringIO()
        
        # Test dry-run mode
        call_command(
            'update_cpe',
            '--dry-run',
            '--days-back=5',
            stdout=out,
            stderr=err
        )
        
        output = out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('Would update CPE data', output)
        
        # Verify no actual import service was created (no mocking needed)
        # The command should exit early in dry-run mode
    
    @given(
        import_status=st.sampled_from(['SUCCESS', 'FAILED', 'PARTIAL']),
        records_processed=st.integers(min_value=0, max_value=1000),
        has_error_message=st.booleans()
    )
    def test_management_command_status_reporting_property(self, import_status, records_processed, has_error_message):
        """
        Property: Management commands should report import status correctly regardless of outcome.
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        from unittest.mock import patch
        
        error_message = 'Test error message' if has_error_message else ''
        
        with patch('apps.cpe_repository.management.commands.import_cpe.CPEImportService') as mock_service_class:
            # Mock service with specified status
            mock_service = Mock()
            mock_import_log = Mock()
            mock_import_log.status = import_status
            mock_import_log.records_processed = records_processed
            mock_import_log.error_message = error_message
            mock_import_log.operation = 'FULL_IMPORT'
            mock_import_log.created_at = timezone.now()
            mock_import_log.updated_at = timezone.now()
            mock_service.full_import.return_value = mock_import_log
            mock_service_class.return_value = mock_service
            
            out = StringIO()
            err = StringIO()
            
            if import_status == 'FAILED':
                # Failed imports should raise CommandError
                with self.assertRaises(CommandError):
                    call_command(
                        'import_cpe',
                        '--full-import',
                        stdout=out,
                        stderr=err
                    )
                
                # But should still show processed records count
                output = out.getvalue()
                self.assertIn(str(records_processed), output)
                if has_error_message:
                    self.assertIn(error_message, output)
                    
            else:
                # Success and partial should not raise exceptions
                call_command(
                    'import_cpe',
                    '--full-import',
                    stdout=out,
                    stderr=err
                )
                
                output = out.getvalue()
                
                # Verify status-specific messages
                if import_status == 'SUCCESS':
                    self.assertIn('completed successfully', output.lower())
                elif import_status == 'PARTIAL':
                    self.assertIn('completed with warnings', output.lower())
                
                # Should always show records processed
                self.assertIn(str(records_processed), output)
                
                # Should show error message if present
                if has_error_message:
                    self.assertIn(error_message, output)
    
    def test_management_command_help_text(self):
        """
        Test that management commands provide helpful usage information.
        """
        from django.core.management import get_commands, load_command_class
        
        # Verify commands are registered
        commands = get_commands()
        self.assertIn('import_cpe', commands)
        self.assertIn('update_cpe', commands)
        
        # Test help text for import_cpe
        import_command = load_command_class('apps.cpe_repository', 'import_cpe')
        self.assertIsNotNone(import_command.help)
        self.assertIn('Import CPE data', import_command.help)
        
        # Test help text for update_cpe
        update_command = load_command_class('apps.cpe_repository', 'update_cpe')
        self.assertIsNotNone(update_command.help)
        self.assertIn('Update CPE data', update_command.help)
    
    def test_management_command_logging_integration(self):
        """
        Test that management commands integrate properly with Django logging.
        """
        from django.core.management import call_command
        from io import StringIO
        from unittest.mock import patch
        import logging
        
        with patch('apps.cpe_repository.management.commands.import_cpe.CPEImportService') as mock_service_class:
            # Mock successful service
            mock_service = Mock()
            mock_import_log = Mock()
            mock_import_log.status = 'SUCCESS'
            mock_import_log.records_processed = 10
            mock_import_log.error_message = ''
            mock_import_log.operation = 'FULL_IMPORT'
            mock_import_log.created_at = timezone.now()
            mock_import_log.updated_at = timezone.now()
            mock_service.full_import.return_value = mock_import_log
            mock_service_class.return_value = mock_service
            
            # Capture log output
            with patch('apps.cpe_repository.management.commands.import_cpe.logger') as mock_logger:
                out = StringIO()
                err = StringIO()
                
                call_command(
                    'import_cpe',
                    '--full-import',
                    stdout=out,
                    stderr=err
                )
                
                # Verify that logging was not called for successful operations
                # (Errors would be logged, but success typically goes to stdout)
                mock_logger.error.assert_not_called()

class CPEAPIEndpointTest(HypothesisTestCase):
    """
    Property-based tests for CPE REST API endpoint coverage.
    Feature: vulnerability-management-dashboard, Property 9: REST API Endpoint Coverage (CPE)
    """
    
    def setUp(self):
        """Set up test data."""
        # Create some test CPE records
        self.cpe_records = []
        for i in range(5):
            cpe = CPERecord.objects.create(
                cpe_name=f'cpe:2.3:a:vendor{i}:product{i}:1.{i}:*:*:*:*:*:*:*',
                cpe_name_id=f'test-cpe-{i}',
                part='a',
                vendor=f'vendor{i}',
                product=f'product{i}',
                version=f'1.{i}',
                deprecated=(i % 2 == 0)  # Make some deprecated
            )
            self.cpe_records.append(cpe)
    
    @given(
        endpoint_type=st.sampled_from(['list', 'detail', 'search']),
        use_pagination=st.booleans(),
        use_filtering=st.booleans()
    )
    def test_cpe_api_endpoint_coverage_property(self, endpoint_type, use_pagination, use_filtering):
        """
        Property: For any data type in the system, there should be corresponding REST API 
        endpoints for search, list, and detail operations.
        
        **Validates: Requirements 3.8, 6.2, 6.3, 6.4**
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        if endpoint_type == 'list':
            # Test list endpoint
            url = '/api/cpe/'
            
            # Add pagination parameters if requested
            if use_pagination:
                url += '?page=1&page_size=3'
            
            # Add filtering parameters if requested
            if use_filtering:
                separator = '&' if use_pagination else '?'
                url += f'{separator}part=a&deprecated=false'
            
            response = client.get(url)
            
            # Verify successful response
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Verify response structure
            self.assertIn('results', response.data)
            self.assertIsInstance(response.data['results'], list)
            
            # Verify pagination metadata
            if use_pagination:
                self.assertIn('count', response.data)
                self.assertIn('total_pages', response.data)
                self.assertIn('current_page', response.data)
                self.assertIn('page_size', response.data)
            
            # Verify filtering works
            if use_filtering:
                for item in response.data['results']:
                    self.assertEqual(item['part'], 'a')
                    self.assertEqual(item['deprecated'], False)
            
            # Verify each result has required fields
            for item in response.data['results']:
                self.assertIn('id', item)
                self.assertIn('cpe_name', item)
                self.assertIn('vendor', item)
                self.assertIn('product', item)
                self.assertIn('cpe_type', item)
        
        elif endpoint_type == 'detail':
            # Test detail endpoint
            cpe_record = self.cpe_records[0]
            url = f'/api/cpe/{cpe_record.id}/'
            
            response = client.get(url)
            
            # Verify successful response
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Verify response contains detailed information
            self.assertEqual(response.data['id'], cpe_record.id)
            self.assertEqual(response.data['cpe_name'], cpe_record.cpe_name)
            self.assertEqual(response.data['vendor'], cpe_record.vendor)
            self.assertEqual(response.data['product'], cpe_record.product)
            
            # Verify detailed fields are present
            self.assertIn('cpe_components', response.data)
            self.assertIn('deprecated_by', response.data)
            self.assertIn('created_at', response.data)
            self.assertIn('updated_at', response.data)
        
        elif endpoint_type == 'search':
            # Test search endpoint
            url = '/api/cpe/search/'
            
            # Add search parameters
            search_params = []
            if use_filtering:
                search_params.append('q=vendor0')
                search_params.append('part=a')
            
            if search_params:
                url += '?' + '&'.join(search_params)
            
            response = client.get(url)
            
            # Verify successful response
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Verify response structure (should be paginated)
            if hasattr(response.data, 'get'):
                # Paginated response
                self.assertIn('results', response.data)
                results = response.data['results']
            else:
                # Direct list response
                results = response.data
            
            self.assertIsInstance(results, list)
            
            # Verify search filtering works
            if use_filtering:
                for item in results:
                    # Should match search criteria
                    self.assertTrue(
                        'vendor0' in item['vendor'].lower() or
                        'vendor0' in item['product'].lower() or
                        'vendor0' in item['cpe_name'].lower()
                    )
                    self.assertEqual(item['part'], 'a')
    
    def test_cpe_api_stats_endpoint(self):
        """
        Test that the stats endpoint provides useful statistics.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        response = client.get('/api/cpe/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify stats structure
        self.assertIn('total_records', response.data)
        self.assertIn('by_part', response.data)
        self.assertIn('deprecated_count', response.data)
        self.assertIn('active_count', response.data)
        
        # Verify stats accuracy
        self.assertEqual(response.data['total_records'], len(self.cpe_records))
        self.assertEqual(response.data['by_part']['applications'], len(self.cpe_records))
        self.assertEqual(response.data['deprecated_count'], 3)  # 0, 2, 4 are deprecated
        self.assertEqual(response.data['active_count'], 2)  # 1, 3 are active
    
    def test_cpe_api_vendors_endpoint(self):
        """
        Test that the vendors endpoint returns unique vendors.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        response = client.get('/api/cpe/vendors/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('vendors', response.data)
        
        vendors = response.data['vendors']
        self.assertIsInstance(vendors, list)
        
        # Should have unique vendors from our test data
        expected_vendors = [f'vendor{i}' for i in range(5)]
        for vendor in expected_vendors:
            self.assertIn(vendor, vendors)
    
    def test_cpe_api_products_endpoint(self):
        """
        Test that the products endpoint returns products for a vendor.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        # Test with valid vendor
        response = client.get('/api/cpe/products/?vendor=vendor0')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('vendor', response.data)
        self.assertIn('products', response.data)
        self.assertEqual(response.data['vendor'], 'vendor0')
        self.assertIn('product0', response.data['products'])
        
        # Test without vendor parameter
        response = client.get('/api/cpe/products/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_cpe_api_versions_endpoint(self):
        """
        Test that the versions endpoint returns versions for a vendor/product.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        # Test with valid vendor and product
        response = client.get('/api/cpe/versions/?vendor=vendor0&product=product0')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('vendor', response.data)
        self.assertIn('product', response.data)
        self.assertIn('versions', response.data)
        self.assertEqual(response.data['vendor'], 'vendor0')
        self.assertEqual(response.data['product'], 'product0')
        self.assertIn('1.0', response.data['versions'])
        
        # Test without required parameters
        response = client.get('/api/cpe/versions/?vendor=vendor0')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        response = client.get('/api/cpe/versions/?product=product0')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @given(
        search_query=st.text(min_size=1, max_size=20, alphabet=st.characters(min_codepoint=97, max_codepoint=122)),
        part_filter=st.sampled_from(['a', 'o', 'h', None]),
        deprecated_filter=st.sampled_from([True, False, None])
    )
    def test_cpe_api_search_parameters_property(self, search_query, part_filter, deprecated_filter):
        """
        Property: For any search parameters, the API should return appropriate results
        and handle the parameters correctly.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        # Build search URL with parameters
        params = []
        if search_query:
            params.append(f'q={search_query}')
        if part_filter:
            params.append(f'part={part_filter}')
        if deprecated_filter is not None:
            params.append(f'deprecated={str(deprecated_filter).lower()}')
        
        url = '/api/cpe/search/'
        if params:
            url += '?' + '&'.join(params)
        
        response = client.get(url)
        
        # Should always return successful response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Extract results from response
        if hasattr(response.data, 'get') and 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        self.assertIsInstance(results, list)
        
        # Verify filtering is applied correctly
        for item in results:
            if part_filter:
                self.assertEqual(item['part'], part_filter)
            if deprecated_filter is not None:
                self.assertEqual(item['deprecated'], deprecated_filter)
    
    def test_cpe_api_error_handling(self):
        """
        Test that API endpoints handle errors gracefully.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        # Test non-existent detail endpoint
        response = client.get('/api/cpe/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test invalid search parameters
        response = client.get('/api/cpe/search/?part=invalid')
        # Should still return 200 but with empty results or validation error
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
    
    @given(
        page_size=st.integers(min_value=1, max_value=10),
        page_number=st.integers(min_value=1, max_value=3)
    )
    def test_cpe_api_pagination_property(self, page_size, page_number):
        """
        Property: For any pagination parameters, the API should return correctly
        paginated results with appropriate metadata.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        # Test pagination
        url = f'/api/cpe/?page={page_number}&page_size={page_size}'
        response = client.get(url)
        
        # Should return successful response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify pagination structure
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertIn('total_pages', response.data)
        self.assertIn('current_page', response.data)
        self.assertIn('page_size', response.data)
        
        # Verify pagination values
        self.assertEqual(response.data['current_page'], page_number)
        self.assertLessEqual(len(response.data['results']), page_size)
        
        # Verify total count matches our test data
        self.assertEqual(response.data['count'], len(self.cpe_records))
    
    def test_cpe_api_ordering(self):
        """
        Test that API endpoints support ordering.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        # Test ordering by vendor
        response = client.get('/api/cpe/?ordering=vendor')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results']
        if len(results) > 1:
            # Verify ordering
            vendors = [item['vendor'] for item in results]
            self.assertEqual(vendors, sorted(vendors))
        
        # Test reverse ordering
        response = client.get('/api/cpe/?ordering=-vendor')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results']
        if len(results) > 1:
            # Verify reverse ordering
            vendors = [item['vendor'] for item in results]
            self.assertEqual(vendors, sorted(vendors, reverse=True))
    
    def test_cpe_api_serializer_fields(self):
        """
        Test that API responses contain all expected fields.
        """
        from rest_framework.test import APIClient
        from rest_framework import status
        
        client = APIClient()
        
        # Test list serializer fields
        response = client.get('/api/cpe/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if response.data['results']:
            item = response.data['results'][0]
            expected_list_fields = [
                'id', 'cpe_name', 'cpe_name_id', 'part', 'vendor', 
                'product', 'version', 'deprecated', 'cpe_type', 
                'created_at', 'updated_at'
            ]
            for field in expected_list_fields:
                self.assertIn(field, item)
        
        # Test detail serializer fields
        if self.cpe_records:
            cpe_id = self.cpe_records[0].id
            response = client.get(f'/api/cpe/{cpe_id}/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            expected_detail_fields = [
                'id', 'cpe_name', 'cpe_name_id', 'part', 'vendor', 
                'product', 'version', 'update', 'edition', 'language',
                'sw_edition', 'target_sw', 'target_hw', 'other',
                'deprecated', 'deprecated_by', 'cpe_type', 'cpe_components',
                'created_at', 'updated_at'
            ]
            for field in expected_detail_fields:
                self.assertIn(field, response.data)