resource "aws_db_instance" "default" {
  allocated_storage    = 10
  db_name              = var.db_name
  engine               = "postgres"
  engine_version       = "15.3-R2"
  instance_class       = "db.t3.micro"
  username             = "mlflow"
  password             = "mlflow_tf"
  parameter_group_name = "default.postgresql15.3"
  skip_final_snapshot  = true
}