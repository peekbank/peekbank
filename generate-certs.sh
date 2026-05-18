#!/usr/bin/env bash
# Generate a self-signed CA + server certificate for the Peekbank MariaDB container.
# Usage: ./generate-certs.sh <ip-or-hostname>
#   e.g. ./generate-certs.sh 34.210.173.143
#
# Produces ./db-certs/{ca,server-cert,server-key}.pem owned by UID 999
# (the mariadb container's mysql user). Refuses to overwrite an existing
# db-certs directory.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <ip-or-hostname>" >&2
  exit 2
fi

SAN="$1"
DIR="./db-certs"
DAYS=3650

if [[ -e "$DIR" ]]; then
  echo "Error: $DIR already exists. Move or remove it before regenerating." >&2
  exit 1
fi

if ! command -v openssl >/dev/null; then
  echo "Error: openssl not found in PATH." >&2
  exit 1
fi

if [[ "$SAN" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN_LINE="IP:$SAN"
else
  SAN_LINE="DNS:$SAN"
fi

mkdir "$DIR"
cd "$DIR"

# 1. Self-signed CA
openssl req -x509 -newkey rsa:4096 -days "$DAYS" -nodes \
  -keyout ca-key.pem -out ca.pem -subj "/CN=peekbank-ca" 2>/dev/null

# 2. Server key + CSR
openssl req -newkey rsa:4096 -nodes -keyout server-key.pem \
  -out server.csr -subj "/CN=peekbank-db" 2>/dev/null

# 3. Sign the server cert with the CA, attaching the SAN
openssl x509 -req -in server.csr -days "$DAYS" \
  -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
  -out server-cert.pem \
  -extfile <(printf "subjectAltName=%s\n" "$SAN_LINE") 2>/dev/null

# Drop artefacts the container doesn't need. The CA key is the only thing
rm -f server.csr ca-key.pem ca.srl ca.pem.srl

# The container's mysql user is UID 999 in the official mariadb image.
if [[ "$(id -u)" -eq 0 ]]; then
  chown 999:999 ca.pem server-cert.pem server-key.pem
else
  echo "Note: not running as root, skipping chown to 999:999."
  echo "      Re-run with sudo if MariaDB inside the container can't read the files."
fi
chmod 600 server-key.pem
chmod 644 ca.pem server-cert.pem

echo
echo "Wrote $PWD/{ca,server-cert,server-key}.pem"
echo
echo "Next steps:"
echo "  1. Uncomment PEEKBANK_TLS_ENABLED in .env"
echo "  2. docker compose up -d peekbank-db"
echo "  3. Distribute ./db-certs/ca.pem to peekbankr maintainers so clients"
echo "     can verify this server."
