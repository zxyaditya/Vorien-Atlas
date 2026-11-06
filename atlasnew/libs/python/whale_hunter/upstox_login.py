import os
import requests
from dotenv import load_dotenv, set_key

load_dotenv()

def main():
    print("========================================")
    print("UPSTOX OAUTH2 LOGIN HELPER")
    print("========================================\n")
    
    api_key = os.getenv("UPSTOX_API_KEY")
    api_secret = os.getenv("UPSTOX_API_SECRET")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI", "https://127.0.0.1")
    
    if not api_key or not api_secret:
        print("ERROR: UPSTOX_API_KEY and UPSTOX_API_SECRET not found in .env file.")
        print("Please create your Upstox App first, add the keys to .env, and run this again.")
        return
        
    login_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
    
    print("Step 1: Open the following URL in your browser and log into Upstox:")
    print(f"\n{login_url}\n")
    
    print("Step 2: After logging in, you will be redirected to an empty or error page (e.g., 127.0.0.1).")
    print("Look at the URL in your browser's address bar. It will look something like this:")
    print("https://127.0.0.1/?code=XXXXXX\n")
    
    code = input("Step 3: Paste the 'code' (the XXXXXX part) here: ").strip()
    
    if not code:
        print("Error: No code provided.")
        return
        
    print("\nExchanging code for access token...")
    
    token_url = "https://api.upstox.com/v2/login/authorization/token"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'code': code,
        'client_id': api_key,
        'client_secret': api_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        # Save to .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        set_key(env_path, "UPSTOX_ACCESS_TOKEN", access_token)
        
        print("\nSUCCESS! Access token generated and saved to .env file.")
        print("You can now run live_engine_india.py!")
    else:
        print(f"\nFAILED! Upstox API Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    main()
