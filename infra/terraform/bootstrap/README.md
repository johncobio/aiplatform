# bootstrap

Creates the Terraform state bucket. Run once per AWS account, with local state:

```
terraform init
terraform apply -var bucket_name=<yourname>-aiplatform-tfstate
```

Cost: a few cents/month. Then put the bucket name into each environment's
`backend.hcl`.
