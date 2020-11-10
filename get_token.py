import requests as rq
from os import environ

subdomen = environ.get('SUBDOMEN')
url_amo_token = f"https://{subdomen}.amocrm.ru/oauth2/access_token"

params_amo_token = {
    "client_id": environ.get('CLIENT_ID'),
    "client_secret": environ.get('CLIENT_SECRET'),
    "grant_type": "authorization_code",
    "code": environ.get('CODE'),
    "redirect_uri": environ.get('SERVER')
}

get_token = rq.post(url_amo_token, data=params_amo_token)
token_response = get_token.json()
print(token_response)

with open('access_token.txt', 'w') as file:
    file.write(token_response['access_token'])

with open('refresh_token.txt', 'w') as file:
    file.write(token_response['refresh_token'])
