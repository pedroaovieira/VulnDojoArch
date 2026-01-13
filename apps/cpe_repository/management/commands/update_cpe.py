"""
Django management command for updating CPE data from NVD.
This is a convenience command that performs incremental updates.
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.cpe_repository.services import CPEImportService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for updating CPE data from NVD API.
    This command performs incremental updates by default.
    
    Usage:
        python manage.py update_cpe
        python manage.py update_cpe --days-back 14
        python manage.py update_cpe --api-key YOUR_API_KEY
    """
    
    help = 'Update CPE data from NVD API (incremental update)'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--days-back',
            type=int,
            default=7,
            help='Number of days to look back for updates (default: 7)'
        )
        
        parser.add_argument(
            '--api-key',
            type=str,
            help='NVD API key for higher rate limits'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        # Set up logging level
        if options['verbose']:
            logging.getLogger('apps.cpe_repository').setLevel(logging.DEBUG)
        
        # Get API key
        api_key = options.get('api_key') or settings.NVD_API_KEY
        days_back = options['days_back']
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would update CPE data for the last {days_back} days'
                )
            )
            if api_key:
                self.stdout.write('Would use provided NVD API key for higher rate limits')
            else:
                self.stdout.write('Would use default rate limits (no API key)')
            return
        
        if not api_key:
            self.stdout.write(
                self.style.WARNING(
                    'No NVD API key provided. Using default rate limits (5 requests per 30 seconds).'
                )
            )
        
        # Create import service
        import_service = CPEImportService(api_key=api_key)
        
        try:
            self.stdout.write(f'Starting CPE update for the last {days_back} days...')
            import_log = import_service.incremental_update(days_back=days_back)
            
            # Report results
            if import_log.status == 'SUCCESS':
                self.stdout.write(
                    self.style.SUCCESS(
                        f'CPE update completed successfully! '
                        f'Updated {import_log.records_processed} records.'
                    )
                )
            elif import_log.status == 'PARTIAL':
                self.stdout.write(
                    self.style.WARNING(
                        f'CPE update completed with warnings. '
                        f'Updated {import_log.records_processed} records. '
                        f'Error: {import_log.error_message}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'CPE update failed! '
                        f'Updated {import_log.records_processed} records. '
                        f'Error: {import_log.error_message}'
                    )
                )
                raise CommandError(f'Update failed: {import_log.error_message}')
                
        except Exception as e:
            logger.error(f'CPE update command failed: {str(e)}')
            raise CommandError(f'Update failed: {str(e)}')
        
        # Display update summary
        if options['verbose']:
            self.stdout.write('\nUpdate Summary:')
            self.stdout.write(f'  Days Back: {days_back}')
            self.stdout.write(f'  Records Updated: {import_log.records_processed}')
            self.stdout.write(f'  Status: {import_log.status}')
            self.stdout.write(f'  Duration: {import_log.updated_at - import_log.created_at}')
            if import_log.error_message:
                self.stdout.write(f'  Errors: {import_log.error_message}')