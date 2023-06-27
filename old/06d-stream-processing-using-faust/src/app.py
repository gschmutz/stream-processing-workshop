import faust

kafka_brokers = ['localhost:29092']

# convenience func for launching the app
def main() -> None:
    app.main()

app = faust.App('truck-pos-app', broker=kafka_brokers)

# GameEvent Schema
class TruckPosition(faust.Record, validation=True, serializer='json'):
    TS: str
    TRUCKID: str
    DRIVERID: int
    ROUTEID: int
    EVENTTYPE: str
    LATITUDE: float
    LONGITUDE: float


rawTruckPosisitonTopic = app.topic('truck_position_json', value_type=TruckPosition)
dangerousDrivingTopic = app.topic('dangerous_driving_faust', value_type=TruckPosition)


@app.agent(rawTruckPosisitonTopic)
async def process(positions):
    async for position in positions:
        print(f'Position for {position.TRUCKID}')
        
        if position.EVENTTYPE != 'Normal': 
            await dangerousDrivingTopic.send( value=position)   


