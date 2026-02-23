# Networking module for Phosphor

variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

# VPC Network
resource "google_compute_network" "main" {
  name                    = "phosphor-network"
  auto_create_subnetworks = false
  project                 = var.project_id
}

# Subnet
resource "google_compute_subnetwork" "main" {
  name          = "phosphor-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.main.id
  project       = var.project_id

  private_ip_google_access = true
}

# Private service connection for Cloud SQL
resource "google_compute_global_address" "private_ip" {
  name          = "phosphor-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
  project       = var.project_id
}

resource "google_service_networking_connection" "private" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

# VPC Connector for Cloud Run
resource "google_vpc_access_connector" "main" {
  name          = "phosphor-connector"
  region        = var.region
  project       = var.project_id
  network       = google_compute_network.main.name
  ip_cidr_range = "10.8.0.0/28"

  min_instances = 2
  max_instances = 3
}

# Outputs
output "network_id" {
  value = google_compute_network.main.id
}

output "network_name" {
  value = google_compute_network.main.name
}

output "subnet_id" {
  value = google_compute_subnetwork.main.id
}

output "private_network" {
  value = google_service_networking_connection.private.network
}

output "vpc_connector_id" {
  value = google_vpc_access_connector.main.id
}
