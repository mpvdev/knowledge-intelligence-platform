resource "aws_s3vectors_vector_bucket" "platform_knowledge" {
  vector_bucket_name = var.vector_bucket_name

  tags = {
    Project   = "Knowledge-Intelligence"
    Component = "VectorSearch"
    ManagedBy = "Terraform"
  }
}

resource "aws_s3vectors_index" "platform_knowledge" {
  vector_bucket_name = aws_s3vectors_vector_bucket.platform_knowledge.vector_bucket_name
  index_name         = var.vector_index_name
  data_type          = "float32"
  dimension          = var.vector_dimensions
  distance_metric    = "cosine"

  metadata_configuration {
    non_filterable_metadata_keys = [
      "document_title",
      "component_name",
      "document_key",
      "embedding_model",
    ]
  }

  tags = {
    Project   = "Knowledge-Intelligence"
    Component = "VectorSearch"
    ManagedBy = "Terraform"
  }
}
