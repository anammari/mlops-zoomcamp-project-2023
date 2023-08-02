import pickle
import xgboost as xgb
from flask import Flask, request, jsonify

# Load the model as a PyFuncModel
logged_model = 'runs:/970c93158be841db8577f63c79f70329/models_mlflow'
booster = mlflow.pyfunc.load_model(logged_model)
return booster


def prepare_features(ride):
    df_features = pd.DataFrame.from_dict([ride])
    return df_features


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