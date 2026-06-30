import json
import datetime
import time
import os
from kafka import KafkaProducer
import random

BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka-1:19092').split(',')
TOPIC = 'energy_produced'


def simulate_energy_production(date: datetime.datetime) -> float:
    hour, minute = date.hour, date.minute
    # Solar production only between 06:00 and 18:00; peaks at noon
    if 6 <= hour <= 18:
        time_factor = max(0, 1 - abs(12 - (hour + minute / 60)) / 6)
    else:
        time_factor = 0

    month = date.month
    if month in (12, 1, 2):
        season_factor = 0.3
    elif month in (3, 4, 5):
        season_factor = 0.5
    elif month in (6, 7, 8):
        season_factor = 0.8
    else:
        season_factor = 0.6

    fluctuation = random.uniform(0.6, 1.0)
    return round(0.05 * time_factor * season_factor * fluctuation, 3)


producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)

if __name__ == '__main__':
    current_time = datetime.datetime(1997, 5, 1, 0, 0, 0)
    try:
        while True:
            for meter_id in range(1, 21):
                energy_produced = simulate_energy_production(current_time)
                data = {
                    'production_time': current_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'meter_id': meter_id,
                    'energy_produced': energy_produced,
                }
                producer.send(TOPIC, json.dumps(data).encode('utf-8'))
            current_time += datetime.timedelta(minutes=1)
            if current_time.day != 1:
                time.sleep(0.8)
    finally:
        producer.flush()
        producer.close()
