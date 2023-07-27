#!/bin/bash
export DB_USER=mlflow
export DB_PASSWORD=<DB_PASSWORD>
export DB_ENDPOINT=<DB_ENDPOINT>
export DB_NAME=<mlflow_db>
export S3_BUCKET_NAME=mlflow-artifacts-remote-ahm-amm
mlflow server -h 0.0.0.0 -p 5000 --backend-store-uri postgresql://$DB_USER:$DB_PASSWORD@$DB_ENDPOINT:5432/$DB_NAME --default-artifact-root s3://$S3_BUCKET_NAME
