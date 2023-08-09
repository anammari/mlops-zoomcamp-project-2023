import pandas as pd
import pickle
import mlflow
import xgboost as xgb
from datetime import datetime, timedelta
import time
import random
import os
import boto3
import s3fs
import io
import psycopg
from prefect import flow, task
from prefect_aws import S3Bucket
from evidently.report import Report
from evidently import ColumnMapping
from evidently.metrics import ColumnDriftMetric, DatasetDriftMetric, DatasetMissingValuesMetric


os.environ['AWS_PROFILE'] = 'default'

mlflow.xgboost.autolog(disable=True)
# Fill TRACKING_SERVER_HOST with the public DNS of the EC2 instance.
TRACKING_SERVER_HOST = "ec2-52-4-31-201.compute-1.amazonaws.com" 
mlflow.set_tracking_uri(f"http://{TRACKING_SERVER_HOST}:5000")
mlflow.set_experiment("monitor-10-wdc-taxi-ride-fair-prediction-s3-pipeline")

SEND_TIMEOUT = 10
rand = random.Random()

create_table_statement = """
drop table if exists ride_metrics;
create table ride_metrics(
  timestamp timestamp,
  prediction_drift float,
  num_drifted_columns integer,
  share_missing_values float
)
"""

begin = None

categorical = ['month_integer', 'dow_integer', 'hour_integer']
numerical = ['origin_block_latitude', 'origin_block_longitude', 'destination_block_latitude', 'destination_block_longitude']
dt_col = ['origindatetime_tr']

column_mapping = ColumnMapping(
    prediction='predicted_amount',
    numerical_features=numerical,
    categorical_features=categorical,
    target=None
)

report = Report(metrics = [
    ColumnDriftMetric(column_name='predicted_amount'),
    DatasetDriftMetric(),
    DatasetMissingValuesMetric()
])

@task(name="Read Data", retries=3, retry_delay_seconds=2)
def read_dataframe(year, month):
    global begin
    begin = datetime(int(year), int(month), 1, 0, 0)
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

@task(name="Read Reference Data", retries=3, retry_delay_seconds=2)
def read_reference():
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
    filename = 'reference.csv'
    df = pd.read_csv(f's3://{S3_BUCKET_NAME}/data/ref/{filename}', storage_options=dict(profile='default'))
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
             'origindatetime_tr', 'month_integer', 'dow_integer', 'hour_integer']]
    return df

@task(name="Load Model", retries=3, retry_delay_seconds=2)
def load_model():
    # Load the model as a PyFuncModel
    logged_model = 'runs:/970c93158be841db8577f63c79f70329/models_mlflow'
    booster = mlflow.pyfunc.load_model(logged_model)
    return booster

@task(name="Preprocess Data", retries=3, retry_delay_seconds=2)
def preprocess(serving_data):
    serving = serving_data[categorical + numerical + dt_col]
    return serving

@task(name="Prepare Database", retries=3, retry_delay_seconds=2)
def prep_db():
  with psycopg.connect("host=localhost port=5432 user=postgres password=example", autocommit=True) as conn:
    res = conn.execute("SELECT 1 FROM pg_database WHERE datname='test'")
    if len(res.fetchall()) == 0:
      conn.execute("create database test;")
    with psycopg.connect("host=localhost port=5432 dbname=test user=postgres password=example") as conn:
      conn.execute(create_table_statement)
      
@task(name="Calculate Metrics", retries=3, retry_delay_seconds=2)
def calculate_metrics_postgresql(serving, ref_df, booster, curr, i):
    global begin
    current_data = serving[(serving.origindatetime_tr >= (begin + timedelta(i))) & \
                           (serving.origindatetime_tr < (begin + timedelta(i + 1)))]
    current_data.drop('origindatetime_tr', axis=1, inplace=True)
    current_data['predicted_amount'] = booster.predict(current_data.fillna(0))
    
    report.run(reference_data = ref_df, current_data = current_data,
               column_mapping=column_mapping)
    
    result = report.as_dict()
    prediction_drift = result['metrics'][0]['result']['drift_score']
    num_drifted_columns = result['metrics'][1]['result']['number_of_drifted_columns']
    share_missing_values = result['metrics'][2]['result']['current']['share_of_missing_values']
    
    curr.execute(
        "insert into ride_metrics(timestamp, prediction_drift, num_drifted_columns, share_missing_values) values (%s, %s, %s, %s)",
        (begin + timedelta(i), prediction_drift, num_drifted_columns, share_missing_values))

    y_pred = current_data['predicted_amount'].to_numpy()
    return (y_pred, current_data)

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
        try:
            mlflow.log_metric("mean_predicted_amount", y_pred.mean())
        except TypeError:
            print("Error: cannot convert the series to <class 'float'>")
        mlflow.set_tag("run_datetime", str(datetime.now()))
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
    # Prepare database
    prep_db()
    last_send = datetime.now() - timedelta(seconds=10)
    # Read the data
    df = read_dataframe(year, month)
    # Read the reference data  
    ref_df = read_reference()
    # Transform the data
    df = transform_data(df)
    # Load the model
    booster = load_model()
    # Preprocess the data
    serving = preprocess(df)
    
    # Make predictions & calculate metrics
    with psycopg.connect("host=localhost port=5432 dbname=test user=postgres password=example", autocommit=True) as conn:
        for i in range(0, 10):
            with conn.cursor() as curr:
                current_df, y_pred = calculate_metrics_postgresql(serving, ref_df, booster, curr, i)
                log_serve_run(current_df, y_pred)
                # Persist the predictions
                write_predictions(y_pred)
            new_send = datetime.now()
            seconds_elapsed = (new_send - last_send).total_seconds()
            if seconds_elapsed < SEND_TIMEOUT:
                time.sleep(SEND_TIMEOUT - seconds_elapsed)
            while last_send < new_send:
                last_send = last_send + timedelta(seconds=10)
                # Log the run details
    
if __name__ == "__main__":
    year = '2019'
    month = '03'
    main(year, month)

