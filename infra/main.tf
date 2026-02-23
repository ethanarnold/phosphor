# Phosphor Infrastructure - Google Cloud Platform
# Phase 1: Staging Environment

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Uncomment for remote state in production
  # backend "gcs" {
  #   bucket = "phosphor-terraform-state"
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# VPC for private services
module "networking" {
  source = "./modules/networking"

  project_id = var.project_id
  region     = var.region
}

# Cloud SQL PostgreSQL with pgvector
module "database" {
  source = "./modules/cloud-sql"

  project_id          = var.project_id
  region              = var.region
  network_id          = module.networking.network_id
  private_network     = module.networking.private_network
  database_name       = "phosphor"
  database_user       = "phosphor"
  tier                = var.database_tier
  availability_type   = var.environment == "production" ? "REGIONAL" : "ZONAL"
  backup_enabled      = true
  deletion_protection = var.environment == "production"

  depends_on = [google_project_service.services]
}

# Memorystore Redis
module "redis" {
  source = "./modules/redis"

  project_id      = var.project_id
  region          = var.region
  network_id      = module.networking.network_id
  memory_size_gb  = var.redis_memory_size
  redis_version   = "REDIS_7_0"

  depends_on = [google_project_service.services]
}

# Secret Manager for sensitive configuration
resource "google_secret_manager_secret" "clerk_secret_key" {
  secret_id = "clerk-secret-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "anthropic-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret" "database_password" {
  secret_id = "database-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

# Cloud Run API service
module "api" {
  source = "./modules/cloud-run"

  project_id      = var.project_id
  region          = var.region
  service_name    = "phosphor-api"
  image           = var.api_image
  vpc_connector   = module.networking.vpc_connector_id
  min_instances   = var.environment == "production" ? 1 : 0
  max_instances   = var.environment == "production" ? 10 : 2

  env_vars = {
    ENVIRONMENT = var.environment
  }

  secrets = {
    DATABASE_URL       = "${google_secret_manager_secret.database_password.id}:latest"
    CLERK_SECRET_KEY   = "${google_secret_manager_secret.clerk_secret_key.id}:latest"
    ANTHROPIC_API_KEY  = "${google_secret_manager_secret.anthropic_api_key.id}:latest"
  }

  database_connection = module.database.connection_name
  redis_host          = module.redis.host
  redis_port          = module.redis.port

  depends_on = [
    google_project_service.services,
    module.database,
    module.redis,
  ]
}

# Cloud Run Worker service (Celery)
module "worker" {
  source = "./modules/cloud-run"

  project_id      = var.project_id
  region          = var.region
  service_name    = "phosphor-worker"
  image           = var.worker_image
  vpc_connector   = module.networking.vpc_connector_id
  min_instances   = var.environment == "production" ? 1 : 0
  max_instances   = var.environment == "production" ? 5 : 1
  is_worker       = true
  command         = ["celery", "-A", "app.tasks", "worker", "--loglevel=info"]

  env_vars = {
    ENVIRONMENT = var.environment
  }

  secrets = {
    DATABASE_URL       = "${google_secret_manager_secret.database_password.id}:latest"
    CLERK_SECRET_KEY   = "${google_secret_manager_secret.clerk_secret_key.id}:latest"
    ANTHROPIC_API_KEY  = "${google_secret_manager_secret.anthropic_api_key.id}:latest"
  }

  database_connection = module.database.connection_name
  redis_host          = module.redis.host
  redis_port          = module.redis.port

  depends_on = [
    google_project_service.services,
    module.database,
    module.redis,
  ]
}

# Outputs
output "api_url" {
  description = "URL of the API service"
  value       = module.api.url
}

output "database_connection" {
  description = "Database connection name"
  value       = module.database.connection_name
  sensitive   = true
}

output "redis_host" {
  description = "Redis host"
  value       = module.redis.host
  sensitive   = true
}
