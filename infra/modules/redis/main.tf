# Memorystore Redis module

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "network_id" {
  type = string
}

variable "memory_size_gb" {
  type    = number
  default = 1
}

variable "redis_version" {
  type    = string
  default = "REDIS_7_0"
}

# Redis instance
resource "google_redis_instance" "main" {
  name           = "phosphor-redis"
  memory_size_gb = var.memory_size_gb
  region         = var.region
  project        = var.project_id

  redis_version = var.redis_version
  tier          = "BASIC"

  authorized_network = var.network_id

  redis_configs = {
    maxmemory-policy = "volatile-lru"
  }

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 4
        minutes = 0
      }
    }
  }
}

# Outputs
output "host" {
  value = google_redis_instance.main.host
}

output "port" {
  value = google_redis_instance.main.port
}

output "instance_name" {
  value = google_redis_instance.main.name
}
