import pandas as pd
import json
import logging
import io
import os
import boto3
from pprint import pprint


def read_files_from_s3(bucket_name, client=None):
    tables=["address", "counterparty", "currency","department", "design","payment",
             "sales_order", "staff"]
    if client is None:
        client = boto3.client("s3") 
    try:
        all_data = {} 
        for table in tables:
            try:
                file_response = client.get_object(Bucket=bucket_name,
                                                Key=f'last_processed/{table}.txt')      
                last_file_processed = file_response["Body"].read().decode("utf-8")      #name of file last processed
                date_last_updated = last_file_processed.split("/",1)[1]             #datetime from the file
                #read the txt file with json file last uploaded from that tables data, date asigned to variable
            except:
                last_file_processed = ""
                date_last_updated = ''     # if no last updated file, define variables and set to min
            try:
                if table == "staff" or table == "address" or table == "counterparty" or table == "department" or table == "currency":
                    response = client.list_objects_v2(Prefix=table ,Bucket=bucket_name)
                else:
                    response = client.list_objects_v2(Prefix=table ,Bucket=bucket_name,MaxKeys=200, StartAfter= last_file_processed)
                #lists the next 50 files to process, from after the last file processed
                if "Contents" not in response:
                    print(f"No files found in {bucket_name}")
                table_data = []

                for object in response["Contents"]:
                    file_key = object["Key"] 
                    file_response = client.get_object(Bucket=bucket_name, Key=file_key)
                
                    if "Body" not in file_response:
                        print(f"⚠️ Skipping {file_key} (no Body in response)")
                        continue
                        #read and load the file into json
                    file_data = file_response["Body"].read().decode("utf-8")
                    file_data = json.loads(file_data)
                    #append dict to table_data list
                    for dict in file_data:
                        table_data.append(dict)
                    #assign the file to the file last processed 
                    last_file_processed = file_key
                all_data[table] = table_data  # append the table_data to the list of all data
            except:
                print(f"No files to process from {table}")
                continue
            #create/overwrite the txt file that had the last_processed date for that table
            client.put_object(
                            Bucket=bucket_name, Key=f'last_processed/{table}.txt',
                            Body=last_file_processed
                        )  
        print(" Successfully retrieved all files.")
        return all_data  

    except Exception as e:
        print(f" Error reading files from {bucket_name}: {e}")
        return {"error": str(e)}  
    
def create_pandas_raw_tables(import_dict):
    info_df_dict = {}

    for file in import_dict:
        info_df = pd.DataFrame(import_dict[file])
        info_df.set_index(list(info_df)[0],inplace=True)
        info_df_dict[file] = info_df
        
    return info_df_dict

# Creates empty dim tables with data types set.
# Returns a dictionary with keys of dim_<table_name>
def create_pandas_empty_dim_tables():
    dim_date_df = pd.DataFrame({
        'date_id': pd.Series(dtype='datetime64[ns]'),
        'year': pd.Series(dtype='int'),
        'month': pd.Series(dtype='int'),
        'day': pd.Series(dtype='int'),
        'day_of_week': pd.Series(dtype='int'),
        'day_name': pd.Series(dtype='str'),
        'month_name': pd.Series(dtype='str'),
        'quarter': pd.Series(dtype='int')
        })
    # The index column is set to the ID value
    dim_date_df.set_index('date_id',inplace=True)
            
    dim_staff_df = pd.DataFrame({
        'staff_id': pd.Series(dtype='int'),
        'first_name': pd.Series(dtype='str'),
        'last_name': pd.Series(dtype='str'),
        'department_name': pd.Series(dtype='str'),
        'location': pd.Series(dtype='str'),
        'email_address': pd.Series(dtype='str')
        })
    dim_staff_df.set_index('staff_id',inplace=True)
            
    dim_location_df = pd.DataFrame({
        'location_id': pd.Series(dtype='int'),
        'address_line_1': pd.Series(dtype='str'),
        'address_line_2': pd.Series(dtype='str'),
        'district': pd.Series(dtype='str'),
        'city': pd.Series(dtype='str'),
        'postal_code': pd.Series(dtype='str'),
        'country': pd.Series(dtype='str'),
        'phone': pd.Series(dtype='str') 
        })
    dim_location_df.set_index('location_id',inplace=True)
            
    dim_currency_df = pd.DataFrame({
        'currency_id': pd.Series(dtype='int'),
        'currency_code': pd.Series(dtype='str'),
        'currency_name': pd.Series(dtype='str') 
        })
    dim_currency_df.set_index('currency_id',inplace=True)
            
    dim_design_df = pd.DataFrame({
        'design_id': pd.Series(dtype='int'),
        'design_name': pd.Series(dtype='str'),
        'file_location': pd.Series(dtype='str'),
        'file_name': pd.Series(dtype='str') 
        })
    dim_design_df.set_index('design_id',inplace=True)
            
    dim_counterparty_df = pd.DataFrame({
        'counterparty_id': pd.Series(dtype='int'),
        'counterparty_legal_name': pd.Series(dtype='str'),
        'counterparty_legal_address_line_1': pd.Series(dtype='str'),
        'counterparty_legal_address_line_2': pd.Series(dtype='str'),
        'counterparty_legal_district': pd.Series(dtype='str'),
        'counterparty_legal_city': pd.Series(dtype='str'),
        'counterparty_legal_postal_code': pd.Series(dtype='str'),
        'counterparty_legal_country': pd.Series(dtype='str'),
        'counterparty_legal_phone_number': pd.Series(dtype='str') 
        })
    dim_counterparty_df.set_index('counterparty_id',inplace=True)

    df_dim_dictionary = {
        'dim_date':dim_date_df,
        'dim_staff':dim_staff_df,
        'dim_location':dim_location_df,
        'dim_currency':dim_currency_df,
        'dim_design':dim_design_df,
        'dim_counterparty':dim_counterparty_df
    }

    print(df_dim_dictionary)
    # return dictionary of dataframes
    return df_dim_dictionary

def populate_dim_dfs(input_info_df,df_dim_dictionary):
    print(input_info_df["currency"], "<<<<<< This is the raw currency data frame")
    # setup output dictionary
    filled_dim_tables = {}
    # dependent tables each dimension table relies on
    dimensions_dependencies = {
    "dim_date":["sales_order"],
    "dim_staff":["staff","department"],
    "dim_location":["address"],
    "dim_currency":["currency"],
    "dim_design":["design"],
    "dim_counterparty":["counterparty","address"]
    }
    # iterate through the keys of the dictionary
    for table_name, dataframe in df_dim_dictionary.items():
        print("Processing TABLE:", table_name)
        if table_name == 'dim_date':
            date_columns = ["created_at"] #, "last_updated", "agreed_delivery_date", "agreed_payment_date"
            all_dates = set()
                # print("DATE>>>>",dates[date])
            for col in date_columns:
                all_dates.update(input_info_df["sales_order"][col].dropna().unique())

            dim_date_df = pd.DataFrame([extract_date_info_from_dim_date(date) for date in all_dates])
            filled_dim_tables[table_name] = dim_date_df
        # run currency operations
        elif table_name == "dim_currency":
            dim_currency_df = input_info_df["currency"].reset_index()  # Fix: Reset index
            dim_currency_df = dim_currency_df[["currency_id", "currency_code"]].copy()  # Extract needed columns
            
            dim_currency_df["currency_name"] = None  # Placeholder if not available

            print("dim_currency_df before adding names:\n", dim_currency_df.head())

            dim_currency_df = add_currency_names(dim_currency_df, input_info_df["currency"])

            filled_dim_tables[table_name] = dim_currency_df

        elif table_name == "dim_design":
            dim_design_df = input_info_df["design"].reset_index()[["design_id", "design_name", "file_location", "file_name"]].copy()
            filled_dim_tables[table_name] = dim_design_df
            
        # process all the other dim tables
        elif table_name in ["dim_staff", "dim_location"]:
            # iterate through the input data staff information
            dim_table = df_dim_dictionary[table_name]
            no_of_dependencies = len(dimensions_dependencies[table_name])
            first_dependency = dimensions_dependencies[table_name][0]
            raw_info_df = input_info_df[first_dependency]

            if no_of_dependencies > 1:
                for i in range(1, no_of_dependencies):
                    merging_dependency = dimensions_dependencies[table_name][i]
                    left_join_key = input_info_df[merging_dependency].index.name
                    merged_df = raw_info_df.merge(input_info_df[merging_dependency], how="left", left_on=left_join_key, right_index=True)
                    dim_table = pd.concat([dim_table, merged_df], ignore_index=False, join="inner")
            else:
                dim_table = pd.concat([dim_table, raw_info_df], ignore_index=False, join="inner")

            filled_dim_tables[table_name] = dim_table

        elif table_name == "dim_counterparty":
            # Ensure both counterparty and address exist in input_info_df
            if "counterparty" in input_info_df and "address" in input_info_df:
                counterparty_df = input_info_df["counterparty"].reset_index()
                address_df = input_info_df["address"]

                # print("Counterparty Columns:", counterparty_df.columns)  # Debugging
                # print("Address Columns:", address_df.columns) 

                # Merge counterparty with address on legal_address_id
                merged_df = counterparty_df.merge(
                    address_df,
                    left_on="legal_address_id",  # Ensure this column exists in counterparty
                    right_on="address_id",
                    how="left"
                )

                # Rename columns to match dim_counterparty schema
                merged_df = merged_df.rename(columns={
                    "counterparty_id": "counterparty_id",
                    "counterparty_legal_name": "counterparty_legal_name",
                    "address_line_1": "counterparty_legal_address_line_1",
                    "address_line_2": "counterparty_legal_address_line_2",
                    "district": "counterparty_legal_district",
                    "city": "counterparty_legal_city",
                    "postal_code": "counterparty_legal_postal_code",
                    "country": "counterparty_legal_country",
                    "phone": "counterparty_legal_phone_number"
                })

                # Select only the required columns
                required_columns = [
                    "counterparty_id",
                    "counterparty_legal_name",
                    "counterparty_legal_address_line_1",
                    "counterparty_legal_address_line_2",
                    "counterparty_legal_district",
                    "counterparty_legal_city",
                    "counterparty_legal_postal_code",
                    "counterparty_legal_country",
                    "counterparty_legal_phone_number"
                ]

                merged_df = merged_df[required_columns]  # Explicit column selection

                # Store transformed DataFrame
                filled_dim_tables[table_name] = merged_df


            else:
                raise ValueError("Missing counterparty or address data in input_info_df")
      
        else:
            # raise exception if dimension table name not valid
            raise Exception(f"Invalid dimension table name: {table_name}")
        
    pprint(filled_dim_tables)
    return filled_dim_tables

def transform_fact_data(raw_data, dim_tables_dict):
    """
    Transforms raw sales_order data into the fact_sales_order schema.

    Args:
        raw_data (dict): Dictionary containing raw sales_order data.
        dim_tables_dict (dict): Dictionary containing dimension tables as Pandas DataFrames.

    Returns:
        pd.DataFrame: Transformed fact_sales_order data.
    """
    try:
        # Ensure sales_order exists in raw data
        if "sales_order" not in raw_data or not raw_data["sales_order"]:
            logging.warning("No sales_order data found in raw data")
            return pd.DataFrame()

        df = pd.DataFrame(raw_data["sales_order"])

        # Convert date-time columns
        df["created_date"] = pd.to_datetime(df["created_at"]).dt.date
        df["created_time"] = pd.to_datetime(df["created_at"]).dt.time
        print(df,"<<<<<DFFFFF")
        df["last_updated_date"] = pd.to_datetime(df["last_updated"]).dt.date
        df["last_updated_time"] = pd.to_datetime(df["last_updated"]).dt.time

       
        # Extract dimension tables from the dictionary
        dim_date = dim_tables_dict.get("dim_date", pd.DataFrame())
        dim_staff = dim_tables_dict.get("dim_staff", pd.DataFrame())
        dim_counterparty = dim_tables_dict.get("dim_counterparty", pd.DataFrame())
        dim_currency = dim_tables_dict.get("dim_currency", pd.DataFrame())
        dim_design = dim_tables_dict.get("dim_design", pd.DataFrame())
        dim_location = dim_tables_dict.get("dim_location", pd.DataFrame())

        # Ensure dim_date has correct format
        if not dim_date.empty and "date_id" in dim_date.columns:
            dim_date["date_id"] = pd.to_datetime(dim_date["date_id"]).dt.date

        # Merge sales_order with dimension tables
        df = df.merge(dim_date, left_on="created_date", right_on="date_id", how="left", suffixes=("", "_created"))
        df = df.merge(dim_date, left_on="last_updated_date", right_on="date_id", how="left", suffixes=("", "_updated"))
        df = df.merge(dim_date, left_on="agreed_payment_date", right_on="date_id", how="left", suffixes=("", "_payment"))
        df = df.merge(dim_date, left_on="agreed_delivery_date", right_on="date_id", how="left", suffixes=("", "_delivery"))
        # Merge with other dimension tables
        df = df.merge(dim_staff, left_on="staff_id", right_index=True, how="left")
        df = df.merge(dim_counterparty, left_on="counterparty_id", right_on="counterparty_id", how="left")
        df = df.merge(dim_currency, left_on="currency_id", right_on="currency_id", how="left")
        df = df.merge(dim_design, left_on="design_id", right_on="design_id", how="left")
        df = df.merge(dim_location, left_on="agreed_delivery_location_id", right_index=True, how="left")
        # Select and rename final columns
        df = df[[
            "sales_order_id","created_date", "created_time", "last_updated_date", "last_updated_time",
            "staff_id", "counterparty_id", "units_sold", "unit_price", "currency_id",
            "design_id", "agreed_payment_date", "agreed_delivery_date", "agreed_delivery_location_id"
        ]]
        df.set_index('sales_order_id',inplace=True)

        # # Optimize memory usage
        # df["sales_order_id"] = df["sales_order_id"].astype("int32")
        # df["staff_id"] = df["staff_id"].astype("int16")
        # df["counterparty_id"] = df["counterparty_id"].astype("int16")
        # df["units_sold"] = df["units_sold"].astype("int32")
        # df["unit_price"] = df["unit_price"].astype("float32")
        # df["currency_id"] = df["currency_id"].astype("int8")
        # df["design_id"] = df["design_id"].astype("int16")
        # df["agreed_delivery_location_id"] = df["agreed_delivery_location_id"].astype("int16")

        fact_sales_order_df = df.drop_duplicates()
        logging.info(f"Transformed sales_order data shape: {fact_sales_order_df.shape}")
        pprint(fact_sales_order_df)

        dim_tables_dict["fact_sales_order"] = fact_sales_order_df

        print(dim_tables_dict)
        return dim_tables_dict

    except Exception as e:
        logging.error(f"Error during sales_order transformation: {e}")
        raise

def write_schema_to_processed(data: dict):

    s3_client = boto3.client("s3")

    bucket_name = os.getenv("S3_BUCKET", S3_BUCKET)

    if not bucket_name:
        raise ValueError(f"{S3_BUCKET} environment variable is not set")
    
    
    
# Set a variable key which dynamically changes the name of each of the pieces of processed data based on one of their unique elements

    try:
        # Convert the files into parquet format
        for table_name,dataframe in data.items():
            source_file = data["source_file"].iloc[0] if "source_file" in dataframe.columns else "unknown_source.json"

            timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

            key = f"{table_name}/{source_file.replace('.json', '')}_{timestamp}.parquet"

            buffer = io.BytesIO()
            dataframe.to_parquet(buffer, engine="pyarrow", index=True)
            buffer.seek(0)

            # Write each file into the S3 processed bucket
            s3_client.put_object(
                Bucket = bucket_name,
                Key = key,
                Body = buffer.getvalue(),
                ContentType = "application/octet-stream"
            )
            print(f"Data successfully written to s3 in parquet format: s3://{bucket_name}/{key}")
    except Exception as e:
        print(f"Error writing to s3: {e}")
        raise

def get_bucket_name(bucket_prefix):
    s3_client = boto3.client('s3')
    list_of_buckets_in_s3 = s3_client.list_buckets(
        BucketRegion="eu-west-2")["Buckets"]
    for bucket in list_of_buckets_in_s3:
        if str(bucket["Name"]).startswith(f"{bucket_prefix}"):
            return bucket["Name"]
    raise Exception(f"No bucket found with prefix {bucket_prefix}")

def lambda_handler(event, context):
    logger.info(":arrows_counterclockwise: Lambda triggered")
    bucket_prefix = os.getenv("BUCKET_PREFIX")
    if not bucket_prefix:
        logger.error("BUCKET_PREFIX environment variable not set")
        return {"statusCode": 500, "body": json.dumps("BUCKET_PREFIX environment variable not set")}

    try:
        bucket_name = get_bucket_name(bucket_prefix)
        files_data = read_files_from_s3(bucket_name)
        raw_pandas_tables = create_pandas_raw_tables(files_data)
        empty_dim_tables = create_pandas_empty_dim_tables()
        dim_dataframes = populate_dim_dfs(raw_pandas_tables, empty_dim_tables)
        final_df = transform_fact_data(raw_pandas_tables, dim_dataframes)
        write_schema_to_processed(final_df, bucket_name)
        return {"statusCode": 200, "body": json.dumps("Data processing successful")}

    except Exception as e:
        logger.error(f"Error processing data: {e}")
        return {"statusCode": 500, "body": json.dumps(f"Error processing data: {e}")}
