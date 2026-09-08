# Credentials Directory

Place your Google Cloud service account JSON file here.

## Setup

1. Create a Google Cloud project
2. Enable the Google Sheets API and Google Drive API
3. Create a service account
4. Download the JSON key file
5. Rename it to `service_account.json`
6. Place it in this directory

## Security

- NEVER commit credential files to version control
- The `.gitignore` file excludes `*.json` and `*.p12` from this directory
- Keep your service account key secure
