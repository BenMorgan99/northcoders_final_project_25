import pytest
import pandas as pd
import boto3
from unittest.mock import patch, MagicMock
from io import BytesIO
from moto import mock_aws
from src.write_to_warehouse import read_from_s3_processed_bucket, write_to_warehouse
import os
import io
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql
from psycopg2.sql import Identifier, SQL
import botocore.exceptions
from utils.get_bucket import get_bucket_name


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
            s3.create_bucket(Bucket="processed-test-bucket", CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})

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

            with patch("utils.get_bucket", return_value="processed-test-bucket"):
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
        s3_client = boto3.client("s3", region_name="eu-west-2")
        bucket_name = "processed-bucket20250303162226216400000005"
        s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})

        table_name = "fact_sales_order"
        old_timestamp = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d_%H-%M-%S")
        new_timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

        old_file_key = f"{table_name}/unknown_source_{old_timestamp}.parquet"
        new_file_key = f"{table_name}/unknown_source_{new_timestamp}.parquet"

        mock_df_old = pd.DataFrame({"col1": [1, 2, 3], "col2": ["x", "y", "z"]})
        mock_df_new = pd.DataFrame({"col1": [4, 5, 6], "col2": ["a", "b", "c"]})

        fake_parquet_old = BytesIO()
        fake_parquet_new = BytesIO()
        mock_df_old.to_parquet(fake_parquet_old, engine="pyarrow", index=False)
        mock_df_new.to_parquet(fake_parquet_new, engine="pyarrow", index=False)

        fake_parquet_old.seek(0)
        fake_parquet_new.seek(0)

        s3_client.put_object(Bucket=bucket_name, Key=old_file_key, Body=fake_parquet_old.getvalue())
        s3_client.put_object(Bucket=bucket_name, Key=new_file_key, Body=fake_parquet_new.getvalue())

        with patch("utils.get_bucket", return_value=bucket_name):
            output = read_from_s3_processed_bucket(s3_client=s3_client)

        pd.testing.assert_frame_equal(output["fact_sales_order"], mock_df_new)

    # test 4 - function attempts to read a corrupted parquet
    @mock_aws
    def test_function_for_corrupted_parquet(self):
        s3_client = boto3.client("s3", region_name="eu-west-2")
        bucket_name = "processed-bucket20250303162226216400000005"
        s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": "eu-west-2"})

        table_name = "fact_sales_order"
        timestamp = "2025-03-06_10-01-45"
        file_key = f"{table_name}/unknown_source_{timestamp}.parquet"

        s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=b"this is not a parquet file")

        with patch("utils.get_bucket", return_value=bucket_name):
            with pytest.raises(Exception, match="Parquet magic bytes not found"):
                read_from_s3_processed_bucket(s3_client=s3_client)


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
            if e.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                raise

        table_name = "fact_sales_order"
        timestamp = "2025-03-06_10-01-45"
        file_key = f"{table_name}/unknown_source_{timestamp}.parquet"

        mock_df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        fake_parquet = BytesIO()
        mock_df.to_parquet(fake_parquet, engine="pyarrow", index=False)
        fake_parquet.seek(0)

        s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=fake_parquet.getvalue())

        with patch("utils.get_bucket", return_value=bucket_name):
            output = read_from_s3_processed_bucket(s3_client=s3_client)

        assert "fact_sales_order" in output
        pd.testing.assert_frame_equal(output["fact_sales_order"], mock_df)
        for table in ["dim_staff", "dim_date", "dim_counterparty", "dim_location"]:
            assert table not in output


class TestWriteToWarehouse:

    @patch("psycopg2.connect")
    @patch("psycopg2.sql.SQL") # Patch the SQL constructor
    def test_write_to_warehouse_success(self, mock_sql_constructor, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        def as_string_side_effect(conn=None):
            return "mocked_sql_string" # return a string.

        mock_sql = MagicMock()
        mock_sql.as_string.side_effect = as_string_side_effect
        mock_sql_constructor.return_value = mock_sql # force the constructor to return our mock.

        mock_data = {
            "table1": pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]}),
            "table2": pd.DataFrame({"col3": [3, 4], "col4": ["c", "d"]}),
        }
        write_to_warehouse(mock_data)

        # Calculate the expected number of execute calls (create table + inserts)
        expected_execute_calls = 6 # 2 tables, create table + 2 rows each
        assert mock_cur.execute.call_count == expected_execute_calls

        # Check commit and close calls
        mock_conn.commit.assert_called_with()
        assert mock_conn.commit.call_count == 2
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("psycopg2.connect")
    @patch("psycopg2.sql.SQL")  # Patch the SQL constructor
    def test_write_to_warehouse_failure(self, mock_sql_constructor, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn

        # Mock the SQL object and its as_string method
        mock_sql = MagicMock()

        def as_string_side_effect(conn=None):
            return "mocked_sql_string"  # Return a string

        mock_sql.as_string.side_effect = as_string_side_effect
        mock_sql_constructor.return_value = mock_sql  # Force the constructor to return our mock

        # Raise the error when cursor.execute is called
        mock_cur.execute.side_effect = psycopg2.OperationalError("Connection failed")
        mock_conn.cursor.return_value = mock_cur

        mock_data = {"table1": pd.DataFrame({"col1": [1], "col2": ["a"]})}

        with pytest.raises(psycopg2.OperationalError, match="Connection failed"):
            write_to_warehouse(mock_data)

        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("psycopg2.connect")
    def test_write_to_warehouse_empty_data(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        write_to_warehouse({})

        mock_cur.execute.assert_not_called()
        mock_conn.commit.assert_not_called()
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()
