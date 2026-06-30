import json
import datetime
import time
import os
from kafka import KafkaProducer
import random

BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka-1:19092').split(',')
TOPIC = 'energy_consumed'


def simulate_energy_consumption(date: datetime.datetime) -> float:
    hour = date.hour
    if 6 <= hour < 9:      # Morning peak
        time_factor = 1.4
    elif 17 <= hour < 21:  # Evening peak
        time_factor = 1.7
    elif 9 <= hour < 17:   # Daytime
        time_factor = 1.2
    else:                   # Nighttime
        time_factor = 0.7
    fluctuation = random.uniform(0.9, 1.1)
    return round(0.025 * time_factor * fluctuation, 3)


producer = KafkaProducer(bootstrap_servers=BOOTSTRAP_SERVERS)

if __name__ == '__main__':
    current_time = datetime.datetime(1997, 5, 1, 0, 0, 0)
    try:
        while True:
            energy_consumed = simulate_energy_consumption(current_time)
            for meter_id in range(1, 21):
                data = {
                    'consumption_time': current_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'meter_id': meter_id,
                    'energy_consumed': energy_consumed,
                }
                producer.send(TOPIC, json.dumps(data).encode('utf-8'))
            current_time += datetime.timedelta(minutes=1)
            # First day runs at full speed to seed historical data quickly
            if current_time.day != 1:
                time.sleep(0.8)
    finally:
        producer.flush()
        producer.close()
