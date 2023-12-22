import azure.functions as func
import logging
import os
from azure.storage.blob import BlobServiceClient
import pandas as pd
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq

app = func.FunctionApp()

@app.blob_trigger(arg_name="myblob", path="staging",
                   connection="BlobStorageConnectionString") 
def blob_staging_trigger(myblob: func.InputStream):

    blob=myblob.name[8:]
    # Log information about the processed blob
    logging.info(f"Python blob trigger function processed blob"
                f"Name: {myblob.name}"
                f"Blob Size: {myblob.length}"
                f"blob: {blob}")

    # Read CSV file from the 'staging' container
    client_report=create_client(container="staging", blob=blob)
    df = blob_to_df(client_report,blob)
    logging.info(f"Report: {df}")

    # Clean the DataFrame
    df = clean(df)
    logging.info(f"Report limpio: {df}")

    # ERP Database
    client_database=create_client(container="database", blob="database_updated.parquet")
    erp = blob_to_df(client_database,"database_updated.parquet")
    logging.info(f"ERP: {erp}")

    # Merge DataFrames based on the 'cups20' column
    merged = pd.merge(df, erp[['cups20','tipo','estado grupo','comercial','nodo','fecha_ed','producto','tarifa resumida', 'equipo']], how="left", on="cups20")
    
    # Fill NaN values with "no firmado"
    merged.fillna("no firmado", inplace=True)
    logging.info(f"merged: {merged}")


    client_report=create_client(container="refined", blob="reporte_estudios.csv")
    df_to_blob(merged,client_report)

def clean(df):
    # Extract the first 20 characters from the 'CUPS' column
    df["cups20"] = df["CUPS"].str[:20]

    # Drop duplicate rows based on the 'cups20' column
    df.drop_duplicates(subset="cups20", inplace=True)

    # Fill NaN values with "-"
    df.fillna("-", inplace=True)

    # Drop rows where 'cups20' is equal to "-"
    df.drop(df[df["cups20"] == "-"].index, inplace=True)

    # Convert 'FECHA' column to datetime and extract the date
    df['FECHA'] = pd.to_datetime(df['FECHA']).dt.date
    
    return df

def create_client(container,blob):
    # Retrieve the connection string from the environment variables
    connection_string = os.environ["BlobStorageConnectionString"]
    
    # Create BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    
    # Get the blob client
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob)

    return blob_client

def blob_to_df(blob_client,blob):

    # Download blob data
    blob_data = blob_client.download_blob()
    data = blob_data.readall()

    # Determine the file format based on the file extension
    file_extension = blob.split('.')[-1].lower()

    # Read the blob data into a DataFrame based on the file format
    if file_extension == 'parquet':
        # Read Parquet file into DataFrame
        df = pd.read_parquet(BytesIO(data))
    elif file_extension == 'csv':
        # Read CSV file into DataFrame
        df = pd.read_csv(BytesIO(data),encoding="cp1252")
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

    return df

def df_to_blob(df,blob_client):

    # Convert DataFrame to CSV in-memory
    csv_data = df.to_csv(index=False)
    csv_data_bytes = csv_data.encode('utf-8')

    # Upload CSV to Blob Storage
    blob_client.upload_blob(csv_data_bytes, overwrite=True)