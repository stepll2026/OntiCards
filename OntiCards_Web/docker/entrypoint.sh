#!/bin/sh

set -e

export NEXT_PUBLIC_DEPLOY_ENV="${DEPLOY_ENV:-PRODUCTION}"
export NEXT_PUBLIC_API_PREFIX="/console/api"
export NEXT_BACKEND_DOMAIN=""
export NEXT_PUBLIC_FILE_PREFIX="/console/api/aiw_chain_file"

exec node ./server.js
