
import psycopg2
from psycopg2 import sql
import sys
import boto3
import os
import pandas as pd
import re
from datetime import datetime
import io
import json
from pprint import pprint
from contextlib import closing
from utils.get_bucket import get_bucket_name

"""
This function should read from the s3 processed bucket then send the data to the data warehouse.

Possibly separate out into:
- s3 read function that reads from processed bucket
- create a warehouse?
- populate warehouse with processed files
"""

PG_USER = "project_team_4"
PG_PASSWORD = "9oOBwGHBqmo161l"
PG_HOST = "nc-data-eng-project-dw-prod.chpsczt8h1nu.eu-west-2.rds.amazonaws.com"
PG_DATABASE = "postgres"
PG_PORT = 5432

# read from s3 processed bucket

table_names = ["fact_sales_order", "dim_staff", "dim_date", "dim_counterparty", "dim_location", "dim_currency", "dim_design"]

def read_from_s3_processed_bucket(s3_client=None):

    bucket_name = get_bucket_name("processed")

    if not s3_client:
        s3_client = boto3.client("s3")

    data_frames_dict = {}

    for table in table_names:
        file_dates_list = []

        objects = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=f"{table}/")
        pprint(objects)
        print( "<<<<< These are the objects")

        if "Contents" not in objects or not objects["Contents"]:
            print(f"No objects found for {table} in S3. Skipping...")
            continue

        for object in objects["Contents"]:
            key = object["Key"]
            print(key, "<<<<<< This is the key")
            filename_timestamp_format = "%Y-%m-%d_%H-%M-%S"

            try:
                filename_timestamp_str = key.split(f"{table}/unknown_source_")[1].split(".parquet")[0] 
                print(filename_timestamp_str, "<<<<<< This is the filename_timestamp_str")
                timestamp = datetime.strptime(filename_timestamp_str, filename_timestamp_format)
                file_dates_list.append((timestamp, key))
            except (IndexError, ValueError):
                print("Skipping file {key} due to unexpected naming format")
                continue

        if not file_dates_list:
            print(f"No valid files found for {table}. Skipping...")
            continue

        file_dates_list.sort(key=lambda tup: tup[0], reverse=True)

        print(file_dates_list, "<<<<< This is the file_dates_list")

        latest_file = file_dates_list[0][1]
        
        latest_file_object = s3_client.get_object(Bucket=bucket_name, Key=latest_file)

        buffer = io.BytesIO(latest_file_object["Body"].read())
        dataframe = pd.read_parquet(buffer, engine="pyarrow")
        data_frames_dict[table] = dataframe

    pprint(data_frames_dict)
    print("<<<<<< These are the dataframe dictionaries")
    return data_frames_dict

# connect to the (redshift?) warehouse, conn=

def write_to_warehouse(data_frames_dict):

    conn = None 
    cur = None
# convert from parquet back to schema
    try:
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD)
        cur = conn.cursor()

        for table_name, df in data_frames_dict.items():
            # creates table if not exists
            try:
                columns = ", ".join(df.columns)
                placeholders = ", ".join(["%s"] * len(df.columns))
                create_table_query = sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} ({})").format(
                    sql.Identifier(table_name), sql.SQL(columns))
                cur.execute(create_table_query.as_string(conn))
                for index, row in df.iterrows():
                    insert_query = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({})").format(
                                sql.Identifier(table_name), sql.SQL(columns), sql.SQL(placeholders))
                    cur.execute(insert_query.as_string(conn), tuple(row))
                print(f"{table_name} successfully written to data warehouse")
                conn.commit()
            except (Exception, psycopg2.DatabaseError) as table_error:
                print(f"Error writing DataFrame '{table_name}': {table_error}")
                raise
            print("All tables processed")
    except (Exception, psycopg2.DatabaseError) as e:
        print(f"Overall database error: {e}")
        raise
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass # if cur.close fails, continue.
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass # if conn.close fails, continue. 
# Insert data into redshift via postgres query
# upload to warehouse in defined intervals
# must be adequately logged in cloudwatch

def lambda_handler(event, context):
    """Lambda handler that orchestrates reading from S3 and writing to the warehouse."""
    try:
        data_frames = read_from_s3_processed_bucket()
        write_to_warehouse(data_frames)

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Data successfully processed and written to warehouse.'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Error processing data: {str(e)}'})
        }

if __name__ == "__main__":
    retrieved_dicts = read_from_s3_processed_bucket()
    write_to_warehouse(retrieved_dicts)
