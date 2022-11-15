
# ensure there is ~/.aws/credentials
if ! grep default $HOME/.aws/credentials > /dev/null; then
cat <<EOF >> $HOME/.aws/credentials
[default]
aws_access_key_id = KEYID
aws_secret_access_key = KEY

EOF
fi

# ensure there is ~/.aws/credentials
if ! grep terraform-stx $HOME/.aws/credentials > /dev/null; then
cat <<EOF >> $HOME/.aws/credentials
[terraform-stx]
role_arn = arn:aws:iam::851772184252:role/terraform_role_adfs
source_profile = default

[terraform-stx-integration]
role_arn = arn:aws:iam::851772184252:role/terraform_role
source_profile = default

EOF
fi

# ensure there is ~/.aws/credentials
if ! grep codecommit-stx $HOME/.aws/credentials > /dev/null; then
cat <<EOF >> $HOME/.aws/credentials
[codecommit-stx]
source_profile = default
role_arn = arn:aws:iam::446236777470:role/codecommit_writer
role_session_name = codecommit_stx
region = eu-central-1

EOF
fi

get_creds_aws