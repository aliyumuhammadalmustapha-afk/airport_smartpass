import os
import django
from datetime import date, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'airport_project.settings')
django.setup()

from flights.models import Flight, Airline

airline = Airline.objects.first()
if not airline:
    airline = Airline.objects.create(name='Max Air', code='VM')

flight = Flight.objects.create(
    airline=airline,
    flight_number='VM' + str(Flight.objects.count() + 100),
    origin='DKA',
    destination='ABJ',
    departure_date=date(2026, 10, 10),
    departure_time=time(19, 30),
    arrival_time=time(20, 30),
    total_seats=60,
    available_seats=60,
    status='scheduled'
)
print(f'Created flight {flight.flight_number} for {flight.departure_date} at {flight.departure_time}')
