#!/bin/bash

set -e

export NEXT_PUBLIC_DEPLOY_ENV=${DEPLOY_ENV}
export NEXT_PUBLIC_API_PREFIX=${CONSOLE_API_URL}/console/api
export NEXT_BACKEND_DOMAIN=${CONSOLE_API_URL}
export NEXT_PUBLIC_FILE_PREFIX=${CONSOLE_API_URL}/aiw_chain_file


node ./server.js
