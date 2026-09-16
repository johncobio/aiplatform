# Copy to staging.tfvars (gitignored). Step 1: apply with enable_compute = false to
# create the network + ECR. Step 2: push an image, then set enable_compute = true.
region         = "us-east-1"
enable_compute = false
image_tag      = ""
allowed_cidrs  = ["203.0.113.10/32"] # your public IP
