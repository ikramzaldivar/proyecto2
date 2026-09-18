output "alb_dns_name" {
  description = "Public DNS name of the load balancer."
  value       = aws_lb.app.dns_name
}

output "cluster_name" {
  description = "ECS cluster that runs the independent frontend and backend services."
  value       = aws_ecs_cluster.app.name
}
