#Creating IAM role for Lambda to access RDS
resource "aws_iam_role" "rds_access_role" {
  name = "rds-access-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com" 
      },
      Action = "sts:AssumeRole"
    }]
  })
}

#iam Policy for RDS and Secrets manager access, 
#needed if rds credentials being stored in secrets manager if not then might not be needed 
resource "aws_iam_policy" "rds_access_policy" {
  name        = "rds-access-policy"
  description = "Allows access to RDS and Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "rds:DescribeDBInstances", #allows lambda to connect to the RDS instance
          "rds:Connect" #allows lambda to get metadata about the database 
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = "*"
      }
    ]
  })
}

#Attach iam policy to iam role
resource "aws_iam_role_policy_attachment" "attach_rds_policy" {
  role       = aws_iam_role.rds_access_role.name
  policy_arn = aws_iam_policy.rds_access_policy.arn
}


#creates lambda and attach iam role to lambda? 
#this is here but will change depending on how lambda 3 set up

# resource "aws_lambda_function" "insert_lambda_name" {
#   function_name = "insert_function_name"
#   role          = aws_iam_role.rds_access_role.arn
#   handler       = "index.handler"
#   runtime       = "python3.8"

#   filename      = "lambda_function.zip"
# }