import argparse
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main():
    parser = argparse.ArgumentParser(description="Upload secrets to Azure Key Vault")
    parser.add_argument("--vault-url", required=True, help="Azure Key Vault URL")
    parser.add_argument("--db-url", required=True, help="PostgreSQL connection string")
    parser.add_argument("--db-async-url", required=True, help="PostgreSQL async connection string")
    parser.add_argument("--groq-key", required=True, help="Groq API Key")
    parser.add_argument("--anthropic-key", required=True, help="Anthropic API Key")
    
    args = parser.parse_args()
    
    print(f"Connecting to Key Vault at {args.vault_url}...")
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=args.vault_url, credential=credential)
    
    secrets = {
        "pg-connection-string": args.db_url,
        "pg-async-connection-string": args.db_async_url,
        "groq-api-key": args.groq_key,
        "anthropic-api-key": args.anthropic_key
    }
    
    for name, value in secrets.items():
        print(f"Setting secret '{name}'...")
        try:
            client.set_secret(name, value)
            print(f"Secret '{name}' set successfully.")
        except Exception as e:
            print(f"Error setting secret '{name}': {e}")
            raise e
            
    print("All secrets successfully uploaded to Key Vault!")

if __name__ == "__main__":
    main()
