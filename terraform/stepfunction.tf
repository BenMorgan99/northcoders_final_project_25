
# resource "aws_sfn_state_machine" "lambda_1_2_3" {
#   name     = "lambda-2-state_machine"
#   role_arn = aws_iam_role.step_function_role.arn
#   definition = jsonencode({
#     "Comment": "State Machine to Process Data from Ingestion to Process Bucket",
#     "StartAt": "ReadFromS3",
#     "States": {
#       "ReadFromS3": {
#         "Type": "Task",
#         "Resource": "${aws_lambda_function.lambda_read_from_ingestion_bucket.arn}",
#         "Parameters": {
#             "Payload":{
#               "input.$": "$"
#             } 
#         },
#         "Next": "CreateTables"
#       },
#         "CreateTables": {
#         "Type": "Task",
#         "Resource": "${aws_lambda_function.lambda_create_tables_pandas_and_dim.arn}",
#         "Parameters": {
#             "Payload":{
#               "input.$": "$"
#             } 
#         }

#         "End": true
#     }
# }
# })
#   depends_on = [aws_lambda_function.lambda_read_from_ingestion_bucket]
# }

# resource "aws_iam_role" "step_function_role" {
#   name = "StepFunctionExecutionRole"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect = "Allow"
#         Principal = {
#           Service = [
#             "states.amazonaws.com",
#             "lambda.amazonaws.com"]
#         }
#         Action = "sts:AssumeRole"
#       }
#     ]
#   })
# }

resource "aws_sfn_state_machine" "lambda_1_2_3" {
  name     = "lambda-2-state_machine"
  role_arn = aws_iam_role.step_function_execution_role.arn
  definition = jsonencode({
    "Comment": "State Machine to Process Data from Ingestion to Process Bucket",
    "StartAt": "ReadFromS3",
    "States": {
      "ReadFromS3": {
        "Type": "Task",
        "Resource": "${aws_lambda_function.lambda_read_from_ingestion_bucket.arn}",
        "Parameters": {
            "Payload":{
              "input.$": "$"
            }
        },
        "Next": "CreateTables"
      },
        "CreateTables": {
        "Type": "Task",
        "Resource": "${aws_lambda_function.lambda_create_tables_pandas_and_dim.arn}",
        "Parameters": {
            "Payload":{
              "input.$": "$"
            }
        },
        "End": true
    }
}
})
  depends_on = [
    aws_lambda_function.lambda_read_from_ingestion_bucket,
    aws_lambda_function.lambda_create_tables_pandas_and_dim,
  ]
}

