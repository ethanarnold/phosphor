# Phosphor Infrastructure Variables

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be staging or production."
  }
}

variable "database_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"  # Use db-custom-2-4096 for production
}

variable "redis_memory_size" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "api_image" {
  description = "Docker image for API service"
  type        = string
  default     = "gcr.io/PROJECT_ID/phosphor-api:latest"
}

variable "worker_image" {
  description = "Docker image for worker service"
  type        = string
  default     = "gcr.io/PROJECT_ID/phosphor-worker:latest"
}
