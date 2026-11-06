import argparse
import sys
from .client import AtlasClient

def main():
    parser = argparse.ArgumentParser(description="Atlas Research Workspace CLI")
    parser.add_argument("--url", default="http://localhost:8000/api", help="Base URL of the Atlas API")
    parser.add_argument("--token", help="Access token for Atlas API")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ping
    subparsers.add_parser("ping", help="Check if the Atlas backend is reachable")
    
    # features
    subparsers.add_parser("features", help="List all features in the registry")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    client = AtlasClient(base_url=args.url, token=args.token)
    
    if args.command == "ping":
        if client.ping():
            print("Successfully connected to Atlas Research Workspace.")
        else:
            print("Failed to connect to Atlas Research Workspace.")
            sys.exit(1)
            
    elif args.command == "features":
        try:
            features = client.list_features()
            print(f"Found {len(features)} features in the registry:")
            for f in features[:10]:  # Just show top 10 for CLI
                print(f" - {f.get('id', 'unknown')}: {f.get('name', 'Unknown Feature')}")
            if len(features) > 10:
                print(f" ... and {len(features) - 10} more.")
        except Exception as e:
            print(f"Error fetching features: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
