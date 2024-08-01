import requests
import base64
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

class AzureADUserFetcher:
    """
    AzureADUserFetcher is a class that interacts with the Microsoft Graph API to retrieve information
    about users in an Azure Active Directory (AD) environment. 

    Purpose is to embed this in a Flask/API to retrieve user details as required in scenarios where the user context (SSO) is not known but the application context itself is trusted.

    Remarks:
    - Usage of Application credentials is discouraged, via on-behalf-of Oauth2 is advised. If all else fails, Application authorization is the only way to go.

    This class performs the following tasks:
    - Obtains an OAuth2 access token using the client credentials flow.
    - Searches for users based on their display name.
    - Retrieves user details including name, email, job title, department, and office location.
    - Can be disabled: Fetches and decodes the user's profile picture (thumbnail) in base64 format, in a thread safe way.

    Usage:
    - The class is initialized with the tenant ID, client ID, and client secret from Azure AD and requires Approved Application authorization

    Author: Christian Wittenberg.
    """
    def __init__(self, tenant_id, client_id, client_secret, retrieve_thumbnails=True):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.graph_endpoint = "https://graph.microsoft.com/v1.0/users"
        self.access_token = self.get_access_token()
        self.retrieve_thumbnails = retrieve_thumbnails

    def get_access_token(self):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        body = {
            'client_id': self.client_id,
            'scope': 'https://graph.microsoft.com/.default',
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        response = requests.post(self.token_url, headers=headers, data=body)
        response.raise_for_status()
        return response.json()['access_token']

    def search_user_by_name(self, name):
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        filter_query = f"startswith(displayName, '{name}')"
        search_url = f"{self.graph_endpoint}?$filter={filter_query}"
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        users = response.json().get('value', [])
        
        user_details = []
        if self.retrieve_thumbnails:
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(self.get_user_thumbnail, user['id']): user for user in users}
                for future in as_completed(futures):
                    user = futures[future]
                    user['Thumbnail'] = future.result()
                    user_details.append(user)
        else:
            user_details = users
        
        return user_details

    def get_user_thumbnail(self, user_id):
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'image/jpg'  # You can specify the image format you expect
        }
        thumbnail_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/photo/$value"
        response = requests.get(thumbnail_url, headers=headers)
        
        if response.status_code == 200:
            # Convert the image to base64
            # you can add "data:image/jpg;base64," to the beginning of below string to embed it in HTML <img> tag as SRC!!!
            image_base64 = base64.b64encode(response.content).decode('utf-8')
            return image_base64
        else:
            return None  # Handle cases where the image is not found



# example, how to use the class - just based on commandline, but you'll want to embed this as Flask API or someting.
if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Search for a user in Azure AD and get their details.")
    parser.add_argument("username", help="The name of the user you want to search for.")
    parser.add_argument("--no-thumbnails", action="store_true", help="Do not retrieve user thumbnails.")
    args = parser.parse_args()

    tenant_id = ''
    client_id = ''
    client_secret = ''

    azure_ad = AzureADUserFetcher(tenant_id, client_id, client_secret, retrieve_thumbnails=not args.no_thumbnails)
    
    # Use the username provided as a command-line argument
    user_name = args.username
    user_info = azure_ad.search_user_by_name(user_name)
    
    if user_info:
        for user in user_info:
            if user.get('Thumbnail'):
                # Decode the base64 string and write it to a .jpg file
                img_data = base64.b64decode(user['Thumbnail'])                

                with open(f"{user['displayName']}.jpg", "wb") as f:
                    f.write(img_data)
                print(f"Thumbnail image saved as {user['displayName']}.jpg")                
            elif args.no_thumbnails:
                print("Thumbnails were not retrieved as per the user request.")
            else:
                print(f"No thumbnail available for {user['displayName']}")

            if 'Thumbnail' in user:
                user.pop('Thumbnail')
                
            print(user)
    else:
        print(f"No user found with the name '{user_name}'")
