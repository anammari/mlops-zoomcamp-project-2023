import requests

ride = {
    "month_integer": 1,
    "dow_integer": 1,
    "hour_integer": 15,
    "origin_block_latitude": 38.983279,
    "origin_block_longitude": -77.026566,
    "destination_block_latitude": 38.905601,
    "destination_block_longitude": -77.062822   
}

url = 'http://localhost:9696/predict'
response = requests.post(url, json=ride)
print(response.json())