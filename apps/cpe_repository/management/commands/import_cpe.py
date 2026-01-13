"""
Django management command for importing CPE data from NVD.
"""
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.cpe_repository.services import CPEImportService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for importing CPE data from NVD API.
    
    Usage:
        python manage.py import_cpe --full-import
        python manage.py import_cpe --incremental --days-back 7
        python manage.py import_cpe --api-key YOUR_API_KEY --full-import
    """
    
    help = 'Import CPE data from NVD API'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--full-import',
            action='store_true',
            help='Perform a full import of all CPE data'
        )
        
        parser.add_argument(
            '--incremental',
            action='store_true',
            help='Perform an incremental update'
        )
        
        parser.add_argument(
            '--days-back',
            type=int,
            default=7,
            help='Number of days to look back for incremental updates (default: 7)'
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
    
    def handle(self, *args, **options):
        """Execute the command."""
        # Set up logging level
        if options['verbose']:
            logging.getLogger('apps.cpe_repository').setLevel(logging.DEBUG)
        
        # Validate arguments
        if not options['full_import'] and not options['incremental']:
            raise CommandError('You must specify either --full-import or --incremental')
        
        if options['full_import'] and options['incremental']:
            raise CommandError('You cannot specify both --full-import and --incremental')
        
        # Get API key
        api_key = options.get('api_key') or settings.NVD_API_KEY
        
        if not api_key:
            self.stdout.write(
                self.style.WARNING(
                    'No NVD API key provided. Using default rate limits (5 requests per 30 seconds).'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    'Using NVD API key. Higher rate limits available (50 requests per 30 seconds).'
                )
            )
        
        # Create import service
        import_service = CPEImportService(api_key=api_key)
        
        try:
            if options['full_import']:
                self.stdout.write('Starting full CPE import...')
                import_log = import_service.full_import()
                
            elif options['incremental']:
                days_back = options['days_back']
                self.stdout.write(f'Starting incremental CPE update (last {days_back} days)...')
                import_log = import_service.incremental_update(days_back=days_back)
            
            # Report results
            if import_log.status == 'SUCCESS':
                self.stdout.write(
                    self.style.SUCCESS(
                        f'CPE import completed successfully! '
                        f'Processed {import_log.records_processed} records.'
                    )
                )
            elif import_log.status == 'PARTIAL':
                self.stdout.write(
                    self.style.WARNING(
                        f'CPE import completed with warnings. '
                        f'Processed {import_log.records_processed} records. '
                        f'Error: {import_log.error_message}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'CPE import failed! '
                        f'Processed {import_log.records_processed} records. '
                        f'Error: {import_log.error_message}'
                    )
                )
                raise CommandError(f'Import failed: {import_log.error_message}')
                
        except Exception as e:
            logger.error(f'CPE import command failed: {str(e)}')
            raise CommandError(f'Import failed: {str(e)}')
        
        # Display import log details
        if options['verbose']:
            self.stdout.write('\nImport Details:')
            self.stdout.write(f'  Operation: {import_log.operation}')
            self.stdout.write(f'  Status: {import_log.status}')
            self.stdout.write(f'  Records Processed: {import_log.records_processed}')
            self.stdout.write(f'  Started: {import_log.created_at}')
            self.stdout.write(f'  Completed: {import_log.updated_at}')
            if import_log.error_message:
                self.stdout.write(f'  Error: {import_log.error_message}')