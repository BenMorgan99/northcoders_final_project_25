Northcoders Final project February/March 2025
==========

# Project Overview
This project aims to extract data from a tote bag store's database, transform it into a structured format, and store it in a data warehouse. A dashboard will use the data warehouse to generate insights for business analysis.

## Tech Stack
* Python (3.10)

* AWS (S3, Lambda, Step Functions, CloudWatch, Secrets Manager, RDS)

* Terraform (Infrastructure as Code)

* PostgreSQL

* GitHub Actions (CI/CD)

* Pandas

  
### Automated Environment Setup
The CI/CD pipeline automates environment configuration:

• Virtual environment setup:

    'python -m venv venv'
    'source venv/bin/activate'

• Dependencies installation:

    'pip install -r requirements.txt'

• Environment variable exports:

    'echo "PG_USER=${{ secrets.PG_USER }}" >> $GITHUB_ENV'


• To trigger workflows:

    Push to main → Runs Terraform Apply

    Pull request to main → Runs Terraform Plan


## Python Pipeline (Automated via GitHub Actions)
This pipeline ensures code quality and runs tests:

• Checkout Repository

• Set up Python 3.10

• Install Dependencies (flake8, pytest, moto, etc.)

• Linting with Flake8

• Run Tests with Pytest (including AWS mocking via moto)

## Terraform Pipeline (Automated via GitHub Actions)
• Checkout Repository

• Configure AWS Credentials

• Set Up Terraform

• Initialize Terraform (terraform init)

• Validate Configuration (terraform validate)


# Documentation
## Terraform
Terraform is used to configure AWS infrastructure. All Terraform files are stored in the terraform/ directory.

### Setting Up Infrastructure (Automated via CI/CD)
• Terraform is initialized and applied automatically in the CI/CD pipeline.

• Manual execution is not required, but for reference, the commands are:

    `terraform init`
    `terraform plan`
    `terraform apply`

• Outputs such as S3 bucket names are exported automatically:

    'export DATA_INGESTION_BUCKET=$(terraform output -raw data_ingestion_bucket)'
    'export DATA_PROCESSED_BUCKET=$(terraform output -raw data_processed_bucket)'

## Key Terraform Files

#### main.tf :
Initializes Terraform workspace, manages backend state in S3 `tf-state-bucket-nc-project-352446`.

#### cloudwatch.tf: 
Configures logging and utilizes cloudwatch to send lambda error and step function failure notifications.

#### eventbridge.tf: 
Schedules and invokes Lambda functions every 5 minutes. (lambda 2 can then write to
`nc-project-schedule`
ingestion bucket if any changes made in rds
attaches iam policy to evenbtridge that allows lambda to be invoked) 

#### data.tf: 
Sets up some commonly used data variables.

#### iam.tf: 
Manages IAM roles and permissions for lambda, cloudwatch logging, event bridge and statefunction.

#### lambda.tf: 
Deploys Lambda functions, zipping and storing code in an S3 bucket. 
(creates three lambda functions and uploads the default test file `index.py` from each of the folders: `raw_data_to_ingestion_bucket`, `ingestion_to_processed_bucket`, `processed_bucket_to_warehouse`. 
Note the lambda file automatically zips the python code into the folder `python_zips` which is then uploaded to the `lambda-code-store-bucket` s3 bucket for execution via lambda.)

#### s3.tf: 
Creates ingestion, processing, and Lambda code storage S3 buckets. 

`ingestion-bucket<random_string>` - stores data brought in from raw database with lambda function 1.

`processed-bucket<random_string>` - stores data which has beeen processed by lambda function 2

`lambda-code-store-bucket<random_string>` - stores all lambda code executed on AWS.

#### secretsmanager.tf: 
Retrieves database credentials from AWS Secrets Manager and stores as a local variable to be used in terraform. No longer in use?

Has policy for read access for secrets manager and attaches the policy to the role.

#### stepfunction.tf: 
Defines a state machine for data processing workflows. Currently set up in test mode to execute a dummy lambda 2 code. The stepfunction is built from the `pipeline.json` file stored in the terraform directory. To update `pipeline.json` use the code view created in the console based aws statemachine setup and paste it into the file.)


##### vars.tf: 
Contains reusable variable definitions. Includes python runtime and naming conventions

#### rds.tf:
Contains 


## Key Scripts 

#### s3_read_function.py 
* Reads data from the ingress bucket and sets as a variable for use in star schema. Currently a test-bucket because lambda 1 is not finalised

#### password_manager.py - 
* Retrieves database credentials from AWS Secrets Manager and stores as a local variable to be used.

#### connection.py
* Creates connection to the database.

####  raw_data_to_ingestions_bucket.py

*`The get_secret():`* function retreieves database credentials from AWS secrets manager and the credentials are used to establish a connection to the database.

*`The lambda_handler(event, context):`* function serves as the entry point for AWS Lambda. It retrieves the credentials, establishes a database connection, calls functions to fetch and process the data, and uploads it to S3.A success message is returned after completing the process.

within the function it queries predefined list of database tables. 
*`list_of_tables():`* 
*`get_file_contents_of_last_uploaded():`* checks for the last_updated timestamp later than the most recently uploaded data (tracked via S3). For each table, it retrieves any new or updated data since the last upload and the 
*`reformat_data_to_json():`* function is used to reformat the data into a JSON format. 

The function reprocesses the data into a list of dictionaries, where each dictionary represents a row with column names as keys.
Timestamps are converted into a consistent format, and decimals are cast to float.

*`update_data_to_s3_bucket():`* function is used for each table, if new or updated data is found, it is uploaded to an S3 bucket.The data is organized in a folder structure based on the table name and the date/time of the upload. A *`last_updated.txt`* file is updated in each table folder to store the key of the most recently uploaded data.

#### updload_to_s3_bucket.py
*`write_to_s3_bucket():`* function is used to upload the data from the list of tables in a postrgeSQL database to an s3 bucket. It connects to the database, then uses the *`list_of_tables()`* function to fetch the list of tables from the database. SQL is used to fetch all the data from all the tables.
*`reformat_data_to_json():`* is called to reformat the data into json files before uploading the data into the s3 bucket. The data is organised by year, month, day and time in the object keys. If an error occurs during the upload process, the function handles the error and returns an appropriate message.


#### write_schema_to_processed.py
* write_schema_to_processed(): * function currently uses hardcoded bucket name for processed s3 bucket. This will likely need changing after each terraform destroy. Function to dynamically fetch bucket based in prefix to be substituted. Pandas is used to create a DataFrame that can then be converted into parquet format. Boto3 then used to write to a file with a dynamic name depending on source_file metadata from respective file in s3 ingestion bucket.

#### update_to_s3_bucket.py

*`get_file_contents_of_last_uploaded():`* function is called to check the most recent uploaded data for each of the tables in the s3 bucket. SQL is used to query the database for records with a last_updated timestamp greater than the most recent timestamp stored in S3. 
 *`reformat_data_to_json():`* is called to convert the database rows into Json files. If new or updated data exists, it uploads the data to the S3 bucket, organizing it by timestamp and creating the appropriate object keys. After each upload, it updates the *`last_updated.txt`* file in the S3 bucket to store the path to the latest uploaded data for each table.

#### fact_sales_order.py

* create_fact_sales_order_table(): * function is called to create the fact_sales_order table and adds foreign key constraints that adhers to key relationships in raw and dim tables.
* transform_fact_data(): * function that transforms raw data from s3 ingestion bucket into star schema format. Pandas used to create a staging table to contain column values found in raw json data. SQL query is then executed which adds the data to the final fact_sales_order table

#### get_currency_name.py
Takes currency_id as an argument and gives both currency_name and currency_code back.


#### Json_data folder
This folder contains all the raw data in json format. Each table is in it's own file within the folder.


### Contribution Guidelines
• Follow the branching convention: feature/<feature-name>

• Run flake8 before committing

• Open a pull request for code reviews before merging







