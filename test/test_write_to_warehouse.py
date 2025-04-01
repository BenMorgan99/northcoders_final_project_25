import pytest
import pandas as pd
import boto3
from unittest.mock import patch, MagicMock
from io import StringIO
from moto import mock_aws
from src.write_to_warehouse import read_from_s3_processed_bucket, write_to_warehouse
import os
import io
from datetime import datetime, timedelta
import psycopg2
import botocore.exceptions
from utils.get_bucket import get_bucket_name



# @pytest.fixture
# def mock_db_connection():
#     with patch("psycopg2.connect") as mock_connect:
#         mock_conn = MagicMock()
#         mock_cur = MagicMock()
#         mock_connect.return_value = mock_conn
#         mock_connect.return_value = mock_cur
#         yield mock_conn, mock_cur

mock_data = {
    "fact_sales_order": pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]}),
    "dim_staff": pd.DataFrame({"col1": [4, 5, 6], "col2": ["d", "e", "f"]}),
}

@pytest.fixture
def mock_db_connection():
    # Mock psycopg2.connect to return a mock connection and cursor
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        # mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        return mock_conn, mock_cur

       

class TestReadFromBucket:
# test 1 - reads file from s3 processed bucket
    @mock_aws
    def test_s3_read_from_bucket(self):
        try:
            s3 = boto3.client("s3", region_name="eu-west-2")
            s3.create_bucket(Bucket="processed-test-bucket")

            # Create test parquet files
            df_data = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
            buffer = io.BytesIO()
            df_data.to_parquet(buffer, engine="pyarrow")
            buffer.seek(0)

            s3.put_object(
                Bucket="processed-test-bucket",
                Key="fact_sales_order/unknown_source_2023-10-26_12-00-00.parquet",
                Body=buffer.getvalue(),
            )
            s3.put_object(
                Bucket="processed-test-bucket",
                Key="dim_staff/unknown_source_2023-10-26_13-00-00.parquet",
                Body=buffer.getvalue(),
            )

            # result_df = pd.read_parquet(io.BytesIO(output["fact_sales_order"]), engine="pyarrow")

            with patch("utils.get_bucket_name", return_value="processed-test-bucket"):
                result = read_from_s3_processed_bucket(s3)

            assert isinstance(result, dict)
            assert "fact_sales_order" in result
            assert "dim_staff" in result
            assert isinstance(result["fact_sales_order"], pd.DataFrame)
            assert len(result["fact_sales_order"]) == 2

  
        except Exception as error:
            pytest.fail(f"Test failed due to: {str(error)}")


    # test 2 - empty bucket contents returns empty dictionary
    @mock_aws
    def test_for_empty_bucket(self):
        try:
            s3_client = boto3.client("s3", region_name="eu-west-2")

            bucket_name = "processed-bucket20250303162226216400000005"

            s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})

            output = read_from_s3_processed_bucket(s3_client=s3_client)

            assert output == {}
        except Exception as error:
            pytest.fail(f"Test failed due to: {str(error)}")


    # test 3 - function reads and extracts most recent file
    @mock_aws
    def test_function_extracts_most_recent_file(self):
        try:
            s3_client = boto3.client("s3", region_name="eu-west-2")
            bucket_name = "processed-bucket20250303162226216400000005"
            s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})

            table_name = "fact_sales_order"
            
            # Create two timestamps, one older and one newer
            old_timestamp = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d_%H-%M-%S")
            new_timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

            old_file_key = f"{table_name}/{table_name}_{old_timestamp}.parquet"
            new_file_key = f"{table_name}/{table_name}_{new_timestamp}.parquet"

            # Create fake Parquet data
            mock_df_old = pd.DataFrame({"col1": [1, 2, 3], "col2": ["x", "y", "z"]})
            mock_df_new = pd.DataFrame({"col1": [4, 5, 6], "col2": ["a", "b", "c"]})

            fake_parquet_old = io.BytesIO()
            fake_parquet_new = io.BytesIO()
            mock_df_old.to_parquet(fake_parquet_old, engine="pyarrow", index=False)
            mock_df_new.to_parquet(fake_parquet_new, engine="pyarrow", index=False)
            
            fake_parquet_old.seek(0)
            fake_parquet_new.seek(0)

            # Upload both files to mock bucket
            s3_client.put_object(Bucket=bucket_name, Key=old_file_key, Body=fake_parquet_old.getvalue())
            s3_client.put_object(Bucket=bucket_name, Key=new_file_key, Body=fake_parquet_new.getvalue())

            output = read_from_s3_processed_bucket(s3_client=s3_client)

            # Checks if the latest file was selected
            result_df = output["fact_sales_order"]
            pd.testing.assert_frame_equal(result_df, mock_df_new)
        except Exception as error:
            pytest.fail(f"Test failed due to: {str(error)}")

    # test 4 - function attempts to read a corrupted parquet
    @mock_aws
    def test_function_for_corrupted_parquet(self):
        s3_client = boto3.client("s3", region_name="eu-west-2")
        bucket_name = "processed-bucket20250303162226216400000005"
        s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})

        table_name = "fact_sales_order"
        timestamp = "2025-03-06_10-01-45"
        file_key = f"{table_name}/{table_name}_{timestamp}.parquet"

        # Upload a corrupted "Parquet" file (invalid binary data)
        s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=b"this is not a parquet file")

        # Call the function and expect False for try and exception raised
        try:
            read_from_s3_processed_bucket(s3_client=s3_client)
            assert False, "Expected an exception for a corrupt Parquet file"
        except Exception as e:
            assert "Parquet magic bytes not found" in str(e), f"Unexpected exception: {e}"


    # test 5 - function attempts to read all tables even if some aren't available
    @mock_aws
    def test_function_reads_all_tables(self):
        s3_client = boto3.client("s3", region_name="eu-west-2")
        bucket_name = "processed-bucket20250303162226216400000005"
        try:
            s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"},
        )
        except botocore.exceptions.ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code != "BucketAlreadyOwnedByYou":
                raise  # Re-raise if it's an unexpected error

        # Only uploading a file for fact_sales_order (missing other tables)
        table_name = "fact_sales_order"
        timestamp = "2025-03-06_10-01-45"
        file_key = f"{table_name}/{table_name}_{timestamp}.parquet"

        mock_df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        fake_parquet = io.BytesIO()
        mock_df.to_parquet(fake_parquet, engine="pyarrow", index=False)
        fake_parquet.seek(0)

        s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=fake_parquet.getvalue())

        output = read_from_s3_processed_bucket(s3_client=s3_client)

        # Ensure fact_sales_order is in the output
        assert "fact_sales_order" in output, "Expected 'fact_sales_order' in output"
        pd.testing.assert_frame_equal(output["fact_sales_order"], mock_df)

        # Ensure other tables are missing
        for table in ["dim_staff", "dim_date", "dim_counterparty", "dim_location"]:
            assert table not in output, f"Expected '{table}' to be missing from output"


class TestWriteToWarehouse:

    @patch("psycopg2.connect")
    # test data schema is successfully written to warehouse tds
    def test_write_to_warehouse_success(self, mock_connect, mock_db_connection):
        # Arrange: Set up the mock cursor and connection
        try:
            mock_conn, mock_cur = mock_db_connection
            mock_connect.return_value = mock_conn

            # Simulate what should happen during the database interaction
            mock_cur.fetchall.return_value = [(1, "a"), (2, "b"), (3, "c")]

            mock_data = {"table1": None, "table2": None} 

            # Act: Call the function with the mock data
            write_to_warehouse(mock_data)

            # Assert: Check that the cursor's execute method was called with the correct SQL query
            for table_name in mock_data:
                mock_cur.execute.assert_any_call(f"SELECT * FROM {table_name}")

            # Assert: Verify that fetchall was called after execute (to fetch results)
            mock_cur.fetchall.assert_called()

            # Assert: Verify that the connection and cursor were closed properly
            mock_cur.close.assert_called()
            mock_conn.close.assert_called()
        except Exception as error:
            pytest.fail(f"Test failed due to: {str(error)}")

    @patch("psycopg2.connect")
    def test_write_to_warehouse_failure(self, mock_connect):
        try:
            mock_connect.side_effect = psycopg2.OperationalError("Connection failed")

            with pytest.raises(RuntimeError, match="Warehouse database operation failed: Connection failed"):
                write_to_warehouse({"table1": None})
        except Exception as error:
            pytest.fail(f"Test failed due to: {str(error)}")

    @patch("psycopg2.connect")
    def test_write_to_warehouse_empty_data(self, mock_connect, mock_db_connection):
        try:
            mock_conn, mock_cur = mock_db_connection
            mock_connect.return_value = mock_conn

            write_to_warehouse({})

            mock_cur.execute.assert_not_called()
            mock_cur.close.assert_called()
            mock_conn.close.assert_called()
        except Exception as error:
            pytest.fail(f"Test failed due to: {str(error)}")

            # mock_boto_client.return_value = mock_s3

            # mock_s3.create_bucket(Bucket="test-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})

            # mock_s3.put_object(Bucket="test-bucket", Key="folder/Hello_world.txt", Body="Hello world")

            # response = mock_s3.list_objects_v2(Bucket="test-bucket", Prefix="folder/")

            # mock_s3.get_object(Bucket="test-bucket", Key="folder/Hello_world.txt")

            # print(response)


        # mock_s3.get_object.return_value = {"Body": fake_parquet_data}

        # output = read_from_s3_processed_bucket(s3_client=mock_s3)

        # result_df = pd.read_parquet(io.BytesIO(output["fact_sales_order"]), engine="pyarrow")

        # pd.testing.assert_frame_equal(result_df, mock_df)



        # print(response)

        # mock_s3.list_objects_v2.return_value = {
        # "Contents": [{"Key": "fact_sales_order_2025-03-06_10-01-45.parquet"}]
        # }

        # fake_parquet_data = io.BytesIO()



        # output = read_from_s3_processed_bucket(s3_client=mock_s3)

        # result_df = pd.read_parquet(io.BytesIO(output["fact_sales_order"]), engine="pyarrow")

        # pd.testing.assert_frame_equal(result_df, mock_df)

        # self.assertIn("fact_sales_order", result_df)

        # self.assertIsInstance(result_df["fact_sales_order"], pd.DataFrame)





    # mock_s3 = MagicMock()
    
    # mock_boto_client.return_value = mock_s3
    
    # mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "fact_sales_order_2025-03-06_10-01-45.parquet"}]}

    # mock_df = pd.DataFrame({"column1": [1, 2, 3]})

    # mock_s3.get_object.return_value = {"Body": io.BytesIO(b"dogandcat")} 
    
    # output = read_from_s3_processed_bucket()
    
    # assert output["fact_sales_order"] == b"dogandcat"

    # mock_s3 = MagicMock()





# test 2 - retrieving data from s3 processed bucket
# test 3 - data successfully populated to warehouse
# test 4 - failure exceptions are captured and printed