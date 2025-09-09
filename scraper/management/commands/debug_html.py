from django.core.management.base import BaseCommand
import requests
from bs4 import BeautifulSoup

class Command(BaseCommand):
    help = 'Debug HTML structure of a store page'
    
    def add_arguments(self, parser):
        parser.add_argument('store_id', type=int, help='Store ID to debug')
    
    def handle(self, *args, **options):
        store_id = options['store_id']
        url = f"https://min-repo.com/{store_id}/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all tables
            tables = soup.find_all('table')
            self.stdout.write(f"Found {len(tables)} tables")
            
            for i, table in enumerate(tables):
                self.stdout.write(f"\n--- TABLE {i+1} ---")
                rows = table.find_all('tr')
                self.stdout.write(f"Rows: {len(rows)}")
                
                for j, row in enumerate(rows[:5]):  # Show first 5 rows
                    cells = row.find_all(['td', 'th'])
                    cell_texts = [cell.get_text().strip() for cell in cells]
                    self.stdout.write(f"Row {j+1}: {cell_texts}")
                
                if len(rows) > 5:
                    self.stdout.write(f"... and {len(rows)-5} more rows")
            
            # Also check for other possible data containers
            self.stdout.write(f"\n--- OTHER ELEMENTS ---")
            divs_with_data = soup.find_all('div', class_=lambda x: x and ('data' in x.lower() or 'machine' in x.lower()))
            self.stdout.write(f"Data divs: {len(divs_with_data)}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
