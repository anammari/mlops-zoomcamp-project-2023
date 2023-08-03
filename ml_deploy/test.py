import predict

ride = {
    "month_integer": 1,
    "dow_integer": 1,
    "hour_integer": 15,
    "origin_block_latitude": 38.983279,
    "origin_block_longitude": -77.026566,
    "destination_block_latitude": 38.905601,
    "destination_block_longitude": -77.062822   
}

features = predict.prepare_features(ride)
pred = predict.predict(features)
print(pred)