terraform {
  backend "s3" {
    bucket       = "knowledge-intelligence-platform"
    key          = "terraform.tfstate"
    region       = "ap-south-1"
    use_lockfile = true
  }
}
