import pickle
import xgboost as xgb
from flask import Flask, request, jsonify

# Load the preprocessor and the model
with open("models/preprocessor.b", "rb") as f_in:
    dv = pickle.load(f_in)
with open('models/xgboost_best.bin', 'rb') as f_in:
    booster = pickle.load(f_in)


def prepare_features(ride):
    X_features = dv.transform(ride)
    X_xgb_features = xgb.DMatrix(X_features)
    return X_xgb_features


def predict(features):
    preds = booster.predict(features)
    return float(preds[0])


app = Flask('fare-prediction')


@app.route('/predict', methods=['POST'])
def predict_endpoint():
    ride = request.get_json()

    features = prepare_features(ride)
    pred = predict(features)

    result = {
        'duration': pred
    }

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=9696)