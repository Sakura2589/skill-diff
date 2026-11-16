"""Demo fixture only: print a proposed integration; make no network request."""

ENDPOINT = "https://telemetry.example.invalid/releases"
CREDENTIAL_FILE = ".env"

print(f"Proposed endpoint: {ENDPOINT}; credential source: {CREDENTIAL_FILE}")
