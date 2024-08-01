import requests
import base64
import argparse

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
    - Fetches and decodes the user's profile picture (thumbnail) in base64 format.

    Usage:
    - The class is initialized with the tenant ID, client ID, and client secret from Azure AD and requires Approved Application authorization

    Author: Christian Wittenberg.
    """
        
    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.graph_endpoint = "https://graph.microsoft.com/v1.0/users"
        self.access_token = self.get_access_token()

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
        for user in users:
            details = {
                'Name': user.get('displayName'),
                'Email': user.get('mail'),
                'Role': user.get('jobTitle'),
                'Department': user.get('department'),
                'Location': user.get('officeLocation'),
                'Thumbnail': self.get_user_thumbnail(user.get('id'))
            }
            user_details.append(details)
        
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
            image_base64 = base64.b64encode(response.content).decode('utf-8')
            return image_base64
        else:
            return None  # Handle cases where the image is not found




# Main execution
if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Search for a user in Azure AD and get their details.")
    parser.add_argument("username", help="The name of the user you want to search for.")
    args = parser.parse_args()

    tenant_id = ''
    client_id = ''
    client_secret = ''

    azure_ad = AzureADUserFetcher(tenant_id, client_id, client_secret)
    
    # Use the username provided as a command-line argument
    user_name = args.username
    user_info = azure_ad.search_user_by_name(user_name)
    
    if user_info:
        for user in user_info:
            print(f"User found: {user}")
            if user['Thumbnail']:
                # Decode the base64 string and write it to a .jpg file
                # On the frontend - all you need to do is to embed the base64 in an <img> as data and it would show
                # For demonstrtion purposes just writing it to disk
                img_data = base64.b64decode(user['Thumbnail'])
                with open(f"{user['Name']}.jpg", "wb") as f:
                    f.write(img_data)
                print(f"Thumbnail image saved as {user_name}.jpg")
            else:
                print(f"No thumbnail available for {user['Name']}")
    else:
        print(f"No user found with the name {user_name}")
