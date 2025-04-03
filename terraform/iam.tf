# policy_doc >>> policy >>> role <<< sts:AssumeRole
# aws_iam_policy_document ->aws_iam_policy-> aws_iam_role-> aws_iam_role_policy_attachment

# GLOBALLY USED
# allows roles to access each service with credentials
# indentifiers are called 'service principal name'

# Defines a trust polocy for lambda to assume IAM role for Lambda, S3, Eventbridge and StepFunction
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com","s3.amazonaws.com","scheduler.amazonaws.com","states.amazonaws.com"]
    }
    actions = [
      "sts:AssumeRole"
      ]
  }
}

# policy document containing relevant permissions for cloudwatch logs
data "aws_iam_policy_document" "iam_cloudwatch_log_doc" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "${aws_cloudwatch_log_group.lambda_log.arn}",
      "arn:aws:logs:eu-west-2:122610499526:log-group:/aws/lambda/raw_data_to_ingestion_bucket-function:*"
    ]
  }
}
# Defines policy that allows cloudwatch to log lambda events
resource "aws_iam_policy" "iam_cloudwatch_log" {
  name   = "cloudwatch_log_policy"
  path   = "/"
  policy = data.aws_iam_policy_document.iam_cloudwatch_log_doc.json
}

# LAMBDA 1 - INGESTION
# writes to ingestion s3 and accesses lambda 1
data "aws_iam_policy_document" "iam_ingestion_write_policy_doc" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:UploadPart",
      "s3:GetObject"
    ]
    resources = [
      "${aws_s3_bucket.ingestion_bucket.arn}/*"
    ]
  }
}
# attaches policy doucment to role for Lambda 1
resource "aws_iam_role" "lambda_1_role" {
  name_prefix        = "role-${var.lambda_1_name}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}
# creates policy for allowing files to be written to ingestion bucket
resource "aws_iam_policy" "iam_ingestion_write_policy" {
  name   = "ingestion_write_policy"
  path   = "/"
  policy = data.aws_iam_policy_document.iam_ingestion_write_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "lambda_1_write_policy_attachment" {
  role = aws_iam_role.lambda_1_role.name
  policy_arn = aws_iam_policy.iam_ingestion_write_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_1_cloudwatch_attachment" {
  role = aws_iam_role.lambda_1_role.name
  policy_arn = aws_iam_policy.iam_cloudwatch_log.arn
}


# LAMBDA 2 - INGESTION TO PROCESSED_BUCKET
# reads from ingestion_bucket and writes to processed_bucket

data "aws_iam_policy_document" "iam_processing_policy_doc" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:UploadPart",
      "s3:GetObject"
    ]
    resources = [
      "${aws_s3_bucket.ingestion_bucket.arn}",
      "${aws_s3_bucket.processed_bucket.arn}"
    ]
  }
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
    ]
    resources = [
      "${aws_cloudwatch_log_group.lambda_log.arn}"
    ]
  }
}

resource "aws_iam_role" "lambda_2_role" {
  name_prefix        = "role-${var.lambda_2_name}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "iam_processing_policy" {
  name   = "processing_policy"
  path   = "/"
  policy = data.aws_iam_policy_document.iam_processing_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "lambda_2_read_write_policy_attachment" {
  role = aws_iam_role.lambda_2_role.name
  policy_arn = aws_iam_policy.iam_processing_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_2_cloudwatch_attachment" {
  role = aws_iam_role.lambda_2_role.name
  policy_arn = aws_iam_policy.iam_cloudwatch_log.arn
}

# LAMBDA 3 - PROCESSED_BUCKET TO DATA WAREHOUSE
# reads from processed_bucket
# write to data warehouse???

data "aws_iam_policy_document" "iam_processed_read_policy_doc" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:UploadPart",
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      "${aws_s3_bucket.processed_bucket.arn}"
    ]
  }
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
    ]
    resources = [
      "${aws_cloudwatch_log_group.lambda_log.arn}"
    ]
  }
}

resource "aws_iam_role" "lambda_3_role" {
  name_prefix        = "role-${var.lambda_3_name}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "iam_processed_read_policy" {
  name   = "processed_read_policy"
  path   = "/"
  policy = data.aws_iam_policy_document.iam_processed_read_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "lambda_3_read_policy_attachment" {
  role = aws_iam_role.lambda_3_role.name
  policy_arn = aws_iam_policy.iam_processed_read_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_3_cloudwatch_attachment" {
  role = aws_iam_role.lambda_3_role.name
  policy_arn = aws_iam_policy.iam_cloudwatch_log.arn
}

# EVENTBRIDGE SCHEDULER - RUNS LAMBDA 1 <= EVERY 30 MINS
# accesses eventbridge scheduler

data "aws_iam_policy_document" "iam_event_scheduler_lambda_1_doc" {
  statement {
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      "${aws_lambda_function.lambda_raw_data_to_ingestion_bucket.arn}"
    ]
  }
}

resource "aws_iam_role" "eventbridge_scheduler_role" {
  name_prefix         = "role-lambda-1-event-scheduler"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_policy" "iam_scheduling_policy" {
  name = "event_scheduling_policy"
  path = "/"
  policy = data.aws_iam_policy_document.iam_event_scheduler_lambda_1_doc.json
}

resource "aws_iam_role_policy_attachment" "iam_event_scheduler_attachment" {
  role = aws_iam_role.eventbridge_scheduler_role.name
  policy_arn = aws_iam_policy.iam_scheduling_policy.arn
}

# STATE FUNCTION - FOR LAMBDA 2 FLOW
# invokes lambda_2 and reports to cloudwatch
data "aws_iam_policy_document" "iam_step_function_execution_doc" {
  statement {
    actions = [
      "lambda:InvokeFunction",
      "cloudwatch:CreateLogDelivery",
      "cloudwatch:GetLogDelivery",
      "cloudwatch:UpdateLogDelivery",
      "cloudwatch:DeleteLogDelivery",
      "cloudwatch:ListLogDeliveries",
      "cloudwatch:PutResourcePolicy",
      "cloudwatch:DescribeResourcePolicies",
      "cloudwatch:DescribeLogGroups",
      "logs:PutLogEvents"
    ]
    resources = [
      "${aws_lambda_function.lambda_read_from_ingestion_bucket.arn}",
      "${aws_cloudwatch_log_group.step_function_logs.arn}",
      "${aws_lambda_function.lambda_create_tables_pandas_and_dim.arn}"
    ]
  }
}

resource "aws_iam_policy" "step_function_lambda_invoke" {
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Effect" : "Allow",
        "Action" : "lambda:InvokeFunction",
        "Resource" : "arn:aws:lambda:eu-west-2:122610499526:function:create_tables_pandas_and_dim-function"
      }
    ]
  })
}


resource "aws_iam_role" "step_function_execution_role" {
  name_prefix         = "role-step-function-execution"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "attach_lambda_invoke" {
  role = aws_iam_role.step_function_execution_role.name
  policy_arn = aws_iam_policy.step_function_lambda_invoke.arn
}

resource "aws_iam_policy" "iam_step_function_policy" {
  name = "step_function_policy"
  path = "/"
  policy = data.aws_iam_policy_document.iam_step_function_execution_doc.json
}

resource "aws_iam_role_policy_attachment" "iam_event_step_function_attachment" {
  role = aws_iam_role.step_function_execution_role.name
  policy_arn = aws_iam_policy.iam_step_function_policy.arn
}

resource "aws_iam_role_policy_attachment" "step_function_cloudwatch_attachment" {
  role       = aws_iam_role.step_function_execution_role.name
  policy_arn = aws_iam_policy.iam_cloudwatch_log.arn
}

resource "aws_iam_role_policy_attachment" "step_function_lambda_invoke_attachment" {
  role       = aws_iam_role.step_function_execution_role.name
  policy_arn = aws_iam_policy.iam_step_function_policy.arn
}

# adding relevant permissions for ecr data

data "aws_iam_policy_document" "lambda_ecr_pull_policy_doc" {
  statement {
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetAuthorizationToken",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart"
    ]
    resources = [
      aws_ecr_repository.lambda_image.arn,
      "arn:aws:ecr:eu-west-2:122610499526:repository/${aws_ecr_repository.lambda_image.name}/*"
    ]
  }
}
# creates resource policy that allows Lambda 2 and 3 to read from ecr
resource "aws_iam_policy" "lambda_ecr_pull_policy" {
  name   = "lambda_ecr_pull_policy"
  path   = "/"
  policy = data.aws_iam_policy_document.lambda_ecr_pull_policy_doc.json
}
# attaches the relevant policies to the Lambda roles
resource "aws_iam_role_policy_attachment" "lambda_2_ecr_pull_attachment" {
  role       = aws_iam_role.lambda_2_role.name
  policy_arn = aws_iam_policy.lambda_ecr_pull_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_3_ecr_pull_attachment" {
  role       = aws_iam_role.lambda_3_role.name
  policy_arn = aws_iam_policy.lambda_ecr_pull_policy.arn
}