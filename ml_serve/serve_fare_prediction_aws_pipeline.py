import pandas as pd
import pickle
import mlflow
import xgboost as xgb
from datetime import datetime
import os
import boto3
import s3fs
import io
from prefect import flow, task
from prefect_aws import S3Bucket
from prefect.artifacts import create_markdown_artifact

os.environ['AWS_PROFILE'] = 'default'

mlflow.xgboost.autolog(disable=True)
# Fill TRACKING_SERVER_HOST with the public DNS of the EC2 instance.
TRACKING_SERVER_HOST = "ec2-52-4-31-201.compute-1.amazonaws.com" 
mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:5000")
mlflow.set_experiment("serve-wdc-taxi-ride-fair-prediction-s3-pipeline")

@task(name="Read Data", retries=3, retry_delay_seconds=2)
def read_dataframe(year, month):
    # Setup AWS S3 
    session = boto3.Session(profile_name='default')
    credentials = session.get_credentials()
    aws_access_key_id = credentials.access_key
    aws_secret_access_key = credentials.secret_key
    region_name = session.region_name

    fs = s3fs.S3FileSystem(
        profile='default',
        key=aws_access_key_id,
        secret=aws_secret_access_key,
        client_kwargs={
        'region_name': region_name
    }
    )
    # Read the TXT file using '|' as the delimiter and specifying the column names
    S3_BUCKET_NAME = 'mlflow-artifacts-remote-ahm-amm'
    filename = f'taxi_{year}_{month}.txt'
    df = pd.read_csv(f's3://{S3_BUCKET_NAME}/data/test/{filename}', delimiter='|', storage_options=dict(profile='default'))
    # Extract the required columns
    df = df[['FAREAMOUNT', 'ORIGIN_BLOCK_LATITUDE', 'ORIGIN_BLOCK_LONGITUDE', 'DESTINATION_BLOCK_LATITUDE', 'DESTINATION_BLOCK_LONGITUDE', 'ORIGINDATETIME_TR']]
    # Convert all headers to lowercase
    df.columns = df.columns.str.lower()
    # Drop rows with missing values
    df = df.dropna()
    # Print the resulting DataFrame
    print(df.head(1))
    return df

@task(name="Transform Data", retries=3, retry_delay_seconds=2)
def transform_data(df):
    # Convert ORIGINDATETIME_TR column to pandas datetime format
    df['origindatetime_tr'] = pd.to_datetime(df['origindatetime_tr'])
    # create new columns for month, day of week, and hour
    df['month_integer'] = df['origindatetime_tr'].dt.month
    df['dow_integer'] = df['origindatetime_tr'].dt.dayofweek
    df['hour_integer'] = df['origindatetime_tr'].dt.hour
    # select the final required columns
    df = df[['fareamount', 'origin_block_latitude', 'origin_block_longitude', 'destination_block_latitude', 'destination_block_longitude', 
             'month_integer', 'dow_integer', 'hour_integer']]
    return df

@task(name="Load Model", retries=3, retry_delay_seconds=2)
def load_model():
    # Load the model as a PyFuncModel
    logged_model = 'runs:/970c93158be841db8577f63c79f70329/models_mlflow'
    booster = mlflow.pyfunc.load_model(logged_model)

    return booster

@task(name="Preprocess Data", retries=3, retry_delay_seconds=2)
def preprocess(serving_data):
    categorical = ['month_integer', 'dow_integer', 'hour_integer']
    numerical = ['origin_block_latitude', 'origin_block_longitude', 'destination_block_latitude', 'destination_block_longitude']
    serving = serving_data[categorical + numerical]
    return serving

@task(name="Log Serve Run", retries=3, retry_delay_seconds=2)
def log_serve_run(df, y_pred):
    mlflow.end_run()
    with mlflow.start_run():
        # Add serve tags
        mlflow.set_tag("developer", "ahmad")
        mlflow.set_tag("model", "xgboost_best")
        # Log some variables to mlflow
        mlflow.log_metric("serving_data_row_count", len(df))
        mlflow.log_metric("predictions_row_count", len(y_pred))
        mlflow.log_metric("mean_predicted_amount", y_pred.mean())
        mlflow.set_tag("run_datetime", str(datetime.now()))

        markdown__rmse_report = f"""# ML Serve Run Report
        
        ## Summary
        Fare Prediction Report
        
        ## Run Details
        |   Run Date  | DF Row Count | Predictions Row Count | Mean Predicted Fare |
        |:------------|--------------|-----------------------|--------------------:|
        | {datetime.now().strftime('%Y%m%d')} | {len(df)} | {len(y_pred)} | {y_pred.mean()} |
        """
        create_markdown_artifact(
            key="fare-model-report", markdown=markdown__rmse_report
        )
    mlflow.end_run()
    return None

@task(name="Write Predictions", retries=3, retry_delay_seconds=2)
def write_predictions(y_pred):
    # Persist the predictions
    output_filename = f"predictions_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    output_key = f"data/output/{output_filename}"
    bucket_name = 'mlflow-artifacts-remote-ahm-amm'
    s3 = boto3.client('s3')
    csv_buffer = io.BytesIO()
    pd.DataFrame(y_pred, columns=["predicted_amount"]).to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    s3.upload_fileobj(csv_buffer, bucket_name, output_key)
    
@flow(name="ML Serve Flow")
def main(year, month):
    # Read the data
    df = read_dataframe(year, month)
    # Transform the data
    df = transform_data(df)
    # Load the model
    booster = load_model()
    # Preprocess the data
    serving = preprocess(df)
    # Make predictions
    y_pred = booster.predict(serving)
    # Log the run details
    log_serve_run(df, y_pred)
    # Persist the predictions
    write_predictions(y_pred)
    
if __name__ == "__main__":
    year = '2019'
    month = '01'
    main(year, month)

