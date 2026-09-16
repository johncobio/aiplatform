# dev environment

Root module for the `dev` environment. Estimated cost while fully running:
≈ $14/month (t4g.small + 20 GB gp3 + ECR storage). With `enable_compute = false`
the cost is effectively zero (VPC, subnets and an empty ECR repo are free).

```
cp backend.example.hcl backend.hcl && cp dev.example.tfvars dev.tfvars   # edit both
terraform init -backend-config=backend.hcl
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
...
terraform destroy -var-file=dev.tfvars
```
