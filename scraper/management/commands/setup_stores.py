from django.core.management.base import BaseCommand
from scraper.models import Store

class Command(BaseCommand):
    help = 'Setup initial store data'
    
    def handle(self, *args, **options):
        # Store IDs from your examples
        store_data = [
            {'store_id': 2564229, 'name': 'Sample Store 1', 'prefecture': 'Tokyo'},
            {'store_id': 2583253, 'name': 'Sample Store 2', 'prefecture': 'Osaka'},
            {'store_id': 2582885, 'name': 'Sample Store 3', 'prefecture': 'Kyoto'},
            {'store_id': 2582867, 'name': 'Sample Store 4', 'prefecture': 'Nagoya'},
            {'store_id': 2583824, 'name': 'Sample Store 5', 'prefecture': 'Fukuoka'},
            {'store_id': 2583250, 'name': 'Sample Store 6', 'prefecture': 'Sapporo'},
        ]
        
        created_count = 0
        for data in store_data:
            store, created = Store.objects.get_or_create(
                store_id=data['store_id'],
                defaults={
                    'name': data['name'],
                    'prefecture': data['prefecture'],
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created store: {store}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Setup completed. {created_count} new stores created.')
        )
