# External Resources RDS Module

External Resources module to provision and manage RDS instances in AWS with App-Interface.

## Tech stack

* Terraform CDKTF
* AWS provider
* Random provider
* Python 3.12
* Pydantic

## Development

Ensure `uv` is installed.

Prepare local development environment:

```shell
make dev
```

This will auto create a `venv`, to activate in shell:

```shell
source .venv/bin/activate
```

## Debugging

Export `input.json` via `qontract-cli` and place it in the current project root dir.

```shell
qontract-cli --config $CONFIG external-resources --provisioner $PROVISIONER --provider $PROVIDER --identifier $IDENTIFIER get-input > input.json
```

Get `credentials`

```shell
qontract-cli --config $CONFIG external-resources --provisioner $PROVISIONER --provider $PROVIDER --identifier $IDENTIFIER get-credentials > credentials
```

Optional config `.env`:

```shell
cp .env.example .env
```

Populate `.env` values with absolute path

Export to current shell

```shell
export $(cat .env | xargs)
```

### On Host

Ensure `cdktf` is installed

```shell
npm install --global cdktf-cli@0.20.11
```

Generate terraform config.

```shell
ER_INPUT_FILE="$PWD"/input.json cdktf synth
```

Ensure AWS credentials set in current shell, then use `terraform` to verify.

```shell
cd cdktf.out/stakcs/CDKTF
terraform init
terraform plan -out=plan
terraform show -json plan > plan.json
```

Test validation logic

```shell
cd ../../..
ER_INPUT_FILE="$PWD"/input.json python hooks/validate_plan.py cdktf.out/stacks/CDKTF/plan.json
```

### In Container

Build image first

```shell
make build
```

Start container

```shell
docker run --rm -ti \
  --entrypoint /bin/bash \
  -v $PWD/input.json:/inputs/input.json:Z \
  -v $PWD/credentials:/credentials:Z \
  -e AWS_SHARED_CREDENTIALS_FILE=/credentials \
  er-aws-rds:prod
```

Generate terraform config.

```shell
cdktf synth
```

Use `terraform` to verify.

```shell
cd cdktf.out/stakcs/CDKTF
terraform init
terraform plan -out=plan
terraform show -json plan > plan.json
```

Test validation logic

```shell
cd ../../..
python hooks/validate_plan.py cdktf.out/stacks/CDKTF/plan.json
```
