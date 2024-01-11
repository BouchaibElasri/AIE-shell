
# ensure there is ~/.aws
if [ ! -d  "$HOME/.aws/credentials" ]; then
  mkdir -p "$HOME/.aws" 
fi

# ensure there is ~/.aws/credentials
if ! grep default "$HOME/.aws/credentials" > /dev/null; then
cat <<EOF >> "$HOME/.aws/credentials"
[default]
aws_access_key_id = KEYID
aws_secret_access_key = KEY

EOF
fi

# ensure there is ~/.aws/credentials
if ! grep terraform-AIE "$HOME/.aws/credentials" > /dev/null; then
cat <<EOF >> "$HOME/.aws/credentials"
[terraform-AIE]
role_arn = arn:aws:iam::581394291120:role/terraform_role_adfs
source_profile = default

[terraform-AIE-integration]
role_arn = arn:aws:iam::581394291120:role/terraform_role
source_profile = default

EOF
fi

# ensure there is ~/.aws/credentials
if ! grep codecommit-AIE "$HOME/.aws/credentials" > /dev/null; then
cat <<EOF >> "$HOME/.aws/credentials"
[codecommit-AIE]
source_profile = default
role_arn = arn:aws:iam::581394291120:role/codecommit_writer
role_session_name = codecommit_AIE
region = eu-central-1

EOF
fi

# shellcheck disable=SC2068
get_creds_aws $@
