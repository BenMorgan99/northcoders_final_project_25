# lambda.tf

# Lambda 1 (lambda_raw_data_to_ingestion_bucket) - ZIP deployment
resource "aws_lambda_function" "lambda_raw_data_to_ingestion_bucket" {
  filename      = data.archive_file.zip_raw_data_to_ingestion_bucket.output_path
  function_name = "${var.lambda_1_name}-function"
  role          = aws_iam_role.lambda_1_role.arn
  handler       = "index.lambda_handler"
  runtime       = var.python_runtime
  layers        = [aws_lambda_layer_version.lambda_layer.arn]
  timeout       = 15
  architectures = ["x86_64"]
}

data "archive_file" "zip_raw_data_to_ingestion_bucket" {
  type        = "zip"
  source_dir  = "${path.module}/../${var.lambda_1_name}/"
  output_path = "${path.module}/../python_zips/${var.lambda_1_name}.zip"
}

# Lambda 2 (lambda_read_from_ingestion_bucket) - Container Image deployment
resource "aws_lambda_function" "lambda_read_from_ingestion_bucket" {
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_image.repository_url}:latest"
  function_name = "read-from-ingestion-function"
  role          = aws_iam_role.lambda_2_role.arn
}

# Lambda create tables and dimension (lambda_create_tables_pandas_and_dim) - Container Image deployment
resource "aws_lambda_function" "lambda_create_tables_pandas_and_dim" {
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_image.repository_url}:latest"
  function_name = "create_tables_pandas_and_dim-function"
  role          = aws_iam_role.lambda_2_role.arn
}

# Lambda 3 (lambda_processed_bucket_to_warehouse) - Container Image deployment
resource "aws_lambda_function" "lambda_processed_bucket_to_warehouse" {
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.lambda_image.repository_url}:latest"
  function_name = "${var.lambda_3_name}-function"
  role          = aws_iam_role.lambda_3_role.arn
}

# ECR repository for Docker images
resource "aws_ecr_repository" "lambda_image" {
  name = "lambda-pandas-image"
}

