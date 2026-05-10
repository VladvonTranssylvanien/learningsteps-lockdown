output "vm_private_ip" {
  description = "Private IP of the API VM"
  value       = azurerm_network_interface.vm.private_ip_address
}

output "api_url" {
  description = "URL to reach the LearningSteps API"
  value       = "http://${azurerm_network_interface.vm.private_ip_address}:8000/docs"
}

output "postgresql_fqdn" {
  description = "Fully qualified domain name of the PostgreSQL server"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "ssh_command" {
  description = "Command to SSH into the VM via Azure CLI"
  value       = "az ssh vm -n vm-${var.prefix} -g rg-${var.prefix}"
}
