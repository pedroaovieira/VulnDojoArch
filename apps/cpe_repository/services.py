"""
CPE Repository import services.
"""
import logging
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone
from apps.core.utils import NVDAPIClient
from apps.core.models import ImportLog
from .models import CPERecord

logger = logging.getLogger(__name__)


class CPEImportService:
    """
    Handles CPE data import and updates from NVD API.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the CPE import service.
        
        Args:
            api_key: Optional NVD API key for higher rate limits
        """
        self.client = NVDAPIClient(api_key)
        self.batch_size = 2000  # NVD API max results per page for CPE
    
    def full_import(self) -> ImportLog:
        """
        Perform initial full import of all CPE data.
        
        Returns:
            ImportLog: Record of the import operation
        """
        import_log = ImportLog.objects.create(
            source='CPE',
            operation='FULL_IMPORT',
            status='STARTED'
        )
        
        try:
            logger.info("Starting full CPE import...")
            
            total_processed = 0
            start_index = 0
            
            while True:
                logger.info(f"Fetching CPE batch starting at index {start_index}")
                
                # Fetch batch from NVD API
                response = self.client.get_cpes(
                    start_index=start_index,
                    results_per_page=self.batch_size
                )
                
                # Extract CPE data from response
                products = response.get('products', [])
                if not products:
                    logger.info("No more CPE data to process")
                    break
                
                # Process batch
                batch_processed = self._process_cpe_batch(products)
                total_processed += batch_processed
                
                logger.info(f"Processed {batch_processed} CPE records in this batch")
                
                # Check if we've processed all available records
                total_results = response.get('totalResults', 0)
                if start_index + len(products) >= total_results:
                    logger.info(f"Reached end of CPE data. Total results: {total_results}")
                    break
                
                # Move to next batch
                start_index += len(products)
            
            # Update import log with success
            import_log.status = 'SUCCESS'
            import_log.records_processed = total_processed
            import_log.save()
            
            logger.info(f"Full CPE import completed successfully. Processed {total_processed} records.")
            
        except Exception as e:
            logger.error(f"Full CPE import failed: {str(e)}")
            import_log.status = 'FAILED'
            import_log.error_message = str(e)
            import_log.save()
            raise
        
        return import_log
    
    def incremental_update(self, days_back: int = 7) -> ImportLog:
        """
        Update with recent changes from the last N days.
        
        Args:
            days_back: Number of days to look back for updates
            
        Returns:
            ImportLog: Record of the update operation
        """
        import_log = ImportLog.objects.create(
            source='CPE',
            operation='INCREMENTAL',
            status='STARTED'
        )
        
        try:
            logger.info(f"Starting incremental CPE update for last {days_back} days...")
            
            # Calculate date range for incremental update
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=days_back)
            
            total_processed = 0
            start_index = 0
            
            # Note: NVD CPE API doesn't support date filtering like CVE API
            # For incremental updates, we'll fetch recent data and update existing records
            # This is a simplified approach - in production, you might want to track
            # last modification dates more precisely
            
            while True:
                logger.info(f"Fetching CPE batch starting at index {start_index}")
                
                response = self.client.get_cpes(
                    start_index=start_index,
                    results_per_page=self.batch_size
                )
                
                products = response.get('products', [])
                if not products:
                    break
                
                # Process batch with update logic
                batch_processed = self._process_cpe_batch(products, update_existing=True)
                total_processed += batch_processed
                
                logger.info(f"Updated {batch_processed} CPE records in this batch")
                
                # For incremental updates, we might want to limit the scope
                # This is a simplified implementation
                start_index += len(products)
                
                # Limit incremental updates to avoid processing entire dataset
                if start_index >= 10000:  # Arbitrary limit for incremental updates
                    logger.info("Reached incremental update limit")
                    break
            
            import_log.status = 'SUCCESS'
            import_log.records_processed = total_processed
            import_log.save()
            
            logger.info(f"Incremental CPE update completed. Updated {total_processed} records.")
            
        except Exception as e:
            logger.error(f"Incremental CPE update failed: {str(e)}")
            import_log.status = 'FAILED'
            import_log.error_message = str(e)
            import_log.save()
            raise
        
        return import_log
    
    def _process_cpe_batch(self, products: List[Dict[str, Any]], update_existing: bool = False) -> int:
        """
        Process a batch of CPE records from NVD API response.
        
        Args:
            products: List of CPE product data from NVD API
            update_existing: Whether to update existing records or skip them
            
        Returns:
            Number of records processed
        """
        processed_count = 0
        
        with transaction.atomic():
            for product_data in products:
                try:
                    cpe_data = product_data.get('cpe', {})
                    if not cpe_data:
                        logger.warning(f"No CPE data found in product: {product_data}")
                        continue
                    
                    # Extract and normalize CPE data
                    normalized_data = self._normalize_cpe_data(cpe_data)
                    
                    if update_existing:
                        # Update or create record
                        cpe_record, created = CPERecord.objects.update_or_create(
                            cpe_name_id=normalized_data['cpe_name_id'],
                            defaults=normalized_data
                        )
                        if created:
                            logger.debug(f"Created new CPE record: {cpe_record.cpe_name}")
                        else:
                            logger.debug(f"Updated CPE record: {cpe_record.cpe_name}")
                    else:
                        # Create only if doesn't exist
                        cpe_record, created = CPERecord.objects.get_or_create(
                            cpe_name_id=normalized_data['cpe_name_id'],
                            defaults=normalized_data
                        )
                        if created:
                            logger.debug(f"Created CPE record: {cpe_record.cpe_name}")
                        else:
                            logger.debug(f"CPE record already exists: {cpe_record.cpe_name}")
                    
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing CPE record {product_data}: {str(e)}")
                    continue
        
        return processed_count
    
    def _normalize_cpe_data(self, cpe_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize CPE data from NVD API format to our model format.
        
        Args:
            cpe_data: Raw CPE data from NVD API
            
        Returns:
            Normalized data dictionary for CPERecord model
        """
        # Extract CPE name and parse components
        cpe_name = cpe_data.get('cpeName', '')
        cpe_name_id = cpe_data.get('cpeNameId', '')
        
        # Parse CPE name components (CPE 2.3 format)
        # Format: cpe:2.3:part:vendor:product:version:update:edition:language:sw_edition:target_sw:target_hw:other
        cpe_parts = cpe_name.split(':') if cpe_name else []
        
        # Ensure we have enough parts (CPE 2.3 has 13 parts including the prefix)
        while len(cpe_parts) < 13:
            cpe_parts.append('*')
        
        # Extract deprecation information
        deprecated = cpe_data.get('deprecated', False)
        deprecated_by = cpe_data.get('deprecatedBy', []) if deprecated else None
        
        # Build normalized data
        normalized_data = {
            'cpe_name': cpe_name,
            'cpe_name_id': cpe_name_id,
            'part': cpe_parts[2] if len(cpe_parts) > 2 else '',
            'vendor': self._decode_cpe_component(cpe_parts[3]) if len(cpe_parts) > 3 else '',
            'product': self._decode_cpe_component(cpe_parts[4]) if len(cpe_parts) > 4 else '',
            'version': self._decode_cpe_component(cpe_parts[5]) if len(cpe_parts) > 5 else '',
            'update': self._decode_cpe_component(cpe_parts[6]) if len(cpe_parts) > 6 else '',
            'edition': self._decode_cpe_component(cpe_parts[7]) if len(cpe_parts) > 7 else '',
            'language': self._decode_cpe_component(cpe_parts[8]) if len(cpe_parts) > 8 else '',
            'sw_edition': self._decode_cpe_component(cpe_parts[9]) if len(cpe_parts) > 9 else '',
            'target_sw': self._decode_cpe_component(cpe_parts[10]) if len(cpe_parts) > 10 else '',
            'target_hw': self._decode_cpe_component(cpe_parts[11]) if len(cpe_parts) > 11 else '',
            'other': self._decode_cpe_component(cpe_parts[12]) if len(cpe_parts) > 12 else '',
            'deprecated': deprecated,
            'deprecated_by': deprecated_by,
        }
        
        return normalized_data
    
    def _decode_cpe_component(self, component: str) -> str:
        """
        Decode CPE component from URI encoding.
        
        Args:
            component: CPE component string
            
        Returns:
            Decoded component string
        """
        if not component or component == '*':
            return ''
        
        # Basic CPE decoding - replace common encoded characters
        # This is a simplified implementation; full CPE decoding is more complex
        decoded = component.replace('%20', ' ').replace('%2f', '/').replace('%5c', '\\')
        
        return decoded[:200]  # Truncate to model field length