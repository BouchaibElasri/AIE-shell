# Used to get temporary credentials for using AWS CLI/Terraform/CodeCommit/...
# Source : https://aws.amazon.com/fr/blogs/security/how-to-implement-a-general-solution-for-federated-apicli-access-using-saml-2-0/
# Update : JCB/29.07.2020 : Adapted for secutix usage and multi-profiles
# Update : JCB/26.01.2021 : Add MFA management
# Update : JCB/28.01.2021 : Provide region choice + add expire date + command line args

import sys
import argparse
import boto.sts
import boto.s3
import requests
import getpass
import configparser
import base64
import logging
import xml.etree.ElementTree as ET
import re
from bs4 import BeautifulSoup
from os.path import expanduser
from urllib.parse import urlparse, urlunparse

version = '1.0'

regions = []
regions.append('us-east-1')
regions.append('eu-central-1')
regions.append('eu-west-1')
region = 'eu-central-1'
outputformat = 'json'
awsconfigfile = '/.aws/credentials'
sslverification = True
idpentryurl = 'https://horizon.secutix.com/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices' 
#logging.basicConfig(level=logging.DEBUG)

# Get profile name
parser = argparse.ArgumentParser(usage='use "python %(prog)s --help" for more information',formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('--profile',required=False,help='Profile that will be used later for actions')
parser.add_argument('--region',required=False,help='Region that will be used by this profile')
parser.add_argument('--username',required=False,help='Username to use for authentication')
parser.add_argument('--version', action='version', version='%(prog)s ' + version)
args = parser.parse_args()
profile_name = args.profile
region = args.region
username = args.username
if profile_name is None:
    profile_name = 'saml'

# Get the region
if not region:
    i = 0
    print("Please choose the region you would like to use:")
    for region in regions:
        print('[', i, ']: ', region.split(',')[0])
        i += 1
    print("Selection: ", end=' ')
    selectedregionindex = input()

    # Basic sanity check of input
    if int(selectedregionindex) > (len(regions) - 1):
        print('You selected an invalid region index, please try again')
        sys.exit(0)

    region = regions[int(selectedregionindex)]

# Get the federated credentials from the user
if username is None:
    print("Username:", end=' ')
    username = input()
password = getpass.getpass()
print('')

# Initiate session handler
session = requests.Session()

# Programmatically get the SAML assertion
# Opens the initial IdP url and follows all of the HTTP302 redirects, and
# gets the resulting login page
formresponse = session.get(idpentryurl, verify=sslverification)
# Capture the idpauthformsubmiturl, which is the final url after all the 302s
idpauthformsubmiturl = formresponse.url

# Parse the response and extract all the necessary values
# in order to build a dictionary of all of the form values the IdP expects
formsoup = BeautifulSoup(formresponse.text, 'html.parser')
payload = {}

for inputtag in formsoup.find_all(re.compile('(INPUT|input)')):
    name = inputtag.get('name','')
    value = inputtag.get('value','')

    if "user" in name.lower():
        #Make an educated guess that this is the right field for the username
        payload[name] = username
    elif "email" in name.lower():
        #Some IdPs also label the username field as 'email'
        payload[name] = username
    elif "pass" in name.lower():
        #Make an educated guess that this is the right field for the password
        payload[name] = password
    else:
        #Simply populate the parameter with the existing value (picks up hidden fields in the login form)
        payload[name] = value

# Debug the parameter payload if needed
# Use with caution since this will print sensitive output to the screen
#print payload

# Some IdPs don't explicitly set a form action, but if one is set we should
# build the idpauthformsubmiturl by combining the scheme and hostname 
# from the entry url with the form action target
# If the action tag doesn't exist, we just stick with the 
# idpauthformsubmiturl above
for inputtag in formsoup.find_all(re.compile('(FORM|form)')):
    action = inputtag.get('action')
    loginid = inputtag.get('id')
    if (action and loginid == "loginForm"):
        parsedurl = urlparse(idpentryurl)
        idpauthformsubmiturl = parsedurl.scheme + "://" + parsedurl.netloc + action

# Performs the submission of the IdP login form with the above post data
response = session.post(
    idpauthformsubmiturl, data=payload, verify=sslverification)

# Debug the response if needed
#print (response.text)

# MFA
# Get response content
responsesoup = BeautifulSoup(response.text, 'html.parser')
payload = {}

# Recover variable values to re-post them
for inputtag in responsesoup.find_all(re.compile('(INPUT|input)')):
    name = inputtag.get('name','')
    value = inputtag.get('value','')

    if value:
        payload[name] = value

# Post containing the Context and authentication method (done by javascript in the browser)
response2 = session.post(
    idpauthformsubmiturl, data=payload, verify=sslverification)

formsoup2 = BeautifulSoup(response2.text, 'html.parser')
payload = {}

for inputtag in formsoup2.find_all(re.compile('(INPUT|input)')):
    name = inputtag.get('name','')
    value = inputtag.get('value','')

    if value:
        payload[name] = value

# Add TOTP value to payload
print("Enter your TOTP value:", end=' ')
totp_value = input()
payload["totp"] = totp_value


# Submit totp form
response3 = session.post(
    idpauthformsubmiturl, data=payload, verify=sslverification)

# Overwrite and delete the credential variables, just for safety
username = '##############################################'
password = '##############################################'
del username
del password

# Decode the response and extract the SAML assertion
soup = BeautifulSoup(response3.text, 'html.parser')
assertion = ''

# Look for the SAMLResponse attribute of the input tag (determined by
# analyzing the debug print lines above)
for inputtag in soup.find_all('input'):
    if(inputtag.get('name') == 'SAMLResponse'):
        #print(inputtag.get('value'))
        assertion = inputtag.get('value')

# Better error handling is required for production use.
if (assertion == ''):
    #TODO: Insert valid error checking/handling
    print('Response did not contain a valid SAML assertion or bad TOTP value.')
    sys.exit(0)

# Debug only
# print(base64.b64decode(assertion))

# Parse the returned assertion and extract the authorized roles
awsroles = []
root = ET.fromstring(base64.b64decode(assertion))
for saml2attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
    if (saml2attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role'):
        for saml2attributevalue in saml2attribute.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
            awsroles.append(saml2attributevalue.text)

# Note the format of the attribute value should be role_arn,principal_arn
# but lots of blogs list it as principal_arn,role_arn so let's reverse
# them if needed
for awsrole in awsroles:
    chunks = awsrole.split(',')
    if'saml-provider' in chunks[0]:
        newawsrole = chunks[1] + ',' + chunks[0]
        index = awsroles.index(awsrole)
        awsroles.insert(index, newawsrole)
        awsroles.remove(awsrole)

# If I have more than one role, ask the user which one they want,
# otherwise just proceed
print("")
if len(awsroles) > 1:
    i = 0
    print("Please choose the role you would like to assume:")
    for awsrole in awsroles:
        print('[', i, ']: ', awsrole.split(',')[0])
        i += 1
    print("Selection: ", end=' ')
    selectedroleindex = input()

    # Basic sanity check of input
    if int(selectedroleindex) > (len(awsroles) - 1):
        print('You selected an invalid role index, please try again')
        sys.exit(0)

    role_arn = awsroles[int(selectedroleindex)].split(',')[0]
    principal_arn = awsroles[int(selectedroleindex)].split(',')[1]
else:
    role_arn = awsroles[0].split(',')[0]
    principal_arn = awsroles[0].split(',')[1]

# Use the assertion to get an AWS STS token using Assume Role with SAML
conn = boto.sts.connect_to_region(region)
token = conn.assume_role_with_saml(role_arn=role_arn, principal_arn=principal_arn, saml_assertion=assertion, duration_seconds=43200)

# Write the AWS STS token into the AWS credential file
home = expanduser("~")
filename = home + awsconfigfile

# Read in the existing config file
config = configparser.RawConfigParser()
config.read(filename)

# Put the credentials into a saml specific section instead of clobbering
# the default credentials
if not config.has_section(profile_name):
    config.add_section(profile_name)

config.set(profile_name, '# expire date', token.credentials.expiration)
config.set(profile_name, 'output', outputformat)
config.set(profile_name, 'region', region)
config.set(profile_name, 'aws_access_key_id', token.credentials.access_key)
config.set(profile_name, 'aws_secret_access_key', token.credentials.secret_key)
config.set(profile_name, 'aws_session_token', token.credentials.session_token)

# Write the updated config file
with open(filename, 'w+') as configfile:
    config.write(configfile)

# Give the user some basic info as to what has just happened
print('\n\n----------------------------------------------------------------')
print('Your new access key pair has been stored in the AWS configuration file ' + format(filename) + ' under the ' + format(profile_name) + ' profile.')
print('Note that it will expire at {0}.'.format(token.credentials.expiration))
print('After this time, you may safely rerun this script to refresh your access key pair.')
print('To use this credential, call the AWS CLI with the --profile option (e.g. aws --profile ' + format(profile_name) + ' ec2 describe-instances).')
print('----------------------------------------------------------------\n\n')

# Use the AWS STS token to list all of the S3 buckets
# s3conn = boto.s3.connect_to_region(region,
#                     aws_access_key_id=token.credentials.access_key,
#                     aws_secret_access_key=token.credentials.secret_key,
#                     security_token=token.credentials.session_token)

# buckets = s3conn.get_all_buckets()

# print('Simple API example listing all S3 buckets:')
# print(buckets)
