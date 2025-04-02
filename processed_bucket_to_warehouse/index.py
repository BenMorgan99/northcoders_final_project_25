import json
from write_to_warehouse_from_processed_bucket import read_from_s3_processed_bucket,write_to_warehouse,get_bucket_name,get_secret
import logging

logger = logging.getLogger("MyLogger")
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Lambda handler that orchestrates reading from S3 and writing to the warehouse."""
    try:

        secrets = get_secret()
        conn = psycopg2.connect(
            host=secrets['host'],
            port=secrets['port'],
            database=secrets['database'],
            user=secrets['username'],
            password=secrets['password']
        )
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
