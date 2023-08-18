resource "aws_s3_bucket" "s3_bucket" {
  bucket = var.bucket_name
  acl    = "private"
  force_destroy = true
  tags = {
    Name        = "My MLOps Project bucket"
    Environment = "Dev"
  }
}

output "name" {
  value = aws_s3_bucket.s3_bucket.bucket
}