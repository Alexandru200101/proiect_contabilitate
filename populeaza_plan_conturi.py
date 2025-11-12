# populeaza_plan_conturi.py

import os
import django
import csv
import uuid

# Setatare settings Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'contabilitate.settings')
django.setup()

from decorsoft.models import PlanConturi

# Calea către CSV
file_path = r'D:\Recapitulare\django_invatare\contabilitate\plan_conturi.csv'



with open(file_path, newline='', encoding='cp1252') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        # Folosim get_or_create pentru a evita duplicate
        PlanConturi.objects.get_or_create(
            id=row['id'] if row['id'] else uuid.uuid4(),
            defaults={
                'simbol': row['simbol'] or None,
                'analitic': row['analitic'] or None,
                'denumire': row['denumire'] or None,
                'tip': row['tip'] or None
            }
        )

print("Import finalizat fără duplicate!")



