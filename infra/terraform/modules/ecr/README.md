# ecr

One container repository with immutable tags, scan-on-push, AES256 encryption
and a lifecycle policy (untagged images expire after a day; only the last N
tagged images are kept). Storage cost is $0.10/GB-month; a 10-image history of
~600 MB images is ≈ $0.60/month.
