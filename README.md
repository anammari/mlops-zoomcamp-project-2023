# MLOps Zoomcamp Course Project (cohorts 2023)

## Project Title: TBD

## Problem Statement:

In this MLOps zoomcamp e-course capstone project, we aim to tackle the challenge of estimating the cost for passengers taking regular taxi rides from one location to another within Washington, DC, along with nearby areas in Virginia and Maryland. Leveraging the Washington, DC taxi rides dataset, which comprises historical data from 2015 through 2019, we will build a predictive model to provide accurate fare estimates. The dataset contains comprehensive information on taxi rides that occurred within the boundaries of the DC-area. Participants can access the dataset through the provided [download link](https://opendata.dc.gov/search?categories=transportation&q=taxi&type=document%20link) and will be tasked with employing MLOps techniques and methodologies learned throughout the course to streamline the development, deployment, and monitoring of the machine learning model. By successfully addressing this problem, we can enhance the taxi service experience for both drivers and passengers while demonstrating the practical application of MLOps principles in real-world scenarios.

## Technologies:

- Cloud: AWS + Localstack
- Experiment tracking tools: MLFlow
- Workflow orchestration: Prefect
- Monitoring: Evidently
- CI/CD: Github actions
- Infrastructure as code (IaC): Terraform
- Unit Testing: pytest
- Integration testing: Localstack
- Model training: Pytorch Lightning
- Model tuning: Optuna
- Containerization: Docker

## Data Inputs and Outputs

The ML model for estimating trip fare takes latitude and longitude coordinates as inputs, which correspond to the pickup and drop-off locations of a taxi ride in Washington, DC. These coordinates are then utilized by the ML model to predict the trip fare accurately. The service does not require human-readable addresses for geocoding; instead, it expects direct latitude and longitude values. To interact with the service after the deployment of the ML model into production, users can use a mobile application where they can visually drop pins on a map to specify the pickup and drop-off locations. Alternatively, users may have the option to use geocoding features from services like Google Maps as an alternative input method for specifying locations.

<p align="center">
  <img src="img/data_schema.PNG" alt="Data Schema">
</p>
