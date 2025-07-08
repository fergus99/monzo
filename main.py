from bottle import Bottle, request, response, redirect, run
import os
from json import loads

from monzo.endpoints.pot import Pot
from monzo.authentication import Authentication
from monzo.handlers.filesystem import FileSystem
from monzo.endpoints.account import Account
from monzo.endpoints.pot import MonzoGeneralError


app = Bottle()


target_balance = int(os.environ.get('TARGET_BALANCE'))
pot_name = os.environ.get('POT_NAME')  # Default pot name if not set
client_id=os.environ.get('MONZO_CLIENT_ID')
client_secret=os.environ.get('MONZO_CLIENT_SECRET')
redirect_url=os.environ.get('MONZO_REDIRECT_URL')
tokens_path = os.environ.get('TOKENS_FILE_PATH')

monzo = Authentication(
    client_id=client_id,
    client_secret=client_secret,
    redirect_url=redirect_url,
)

print("starting container1")

try:
    with open(tokens_path, 'r') as f:
    # get authentication from file
        auth_data = loads(f.read())
        monzo = Authentication(
            client_id=client_id,
            client_secret=client_secret,
            redirect_url=redirect_url,
            access_token=auth_data['access_token'],
            access_token_expiry=auth_data['expiry'],
            refresh_token=auth_data['refresh_token'],
        )
except FileNotFoundError as e:
    print(f"Tokens file not found, please log in: {e}")
finally:
    monzo.register_callback_handler(FileSystem(tokens_path))



def get_main_balance():
    return Account.fetch(monzo, account_type='uk_retail')[0].balance

def move_to_pot(auth:Authentication, amount = 0):
    if amount == 0:
        return
    account_id = Account.fetch(auth, account_type='uk_retail')[0].account_id
    pots = Pot.fetch(auth, account_id)
    pot:Pot = next(filter(lambda x: x.deleted is False and x.name == pot_name, pots))
    try:
        if amount > 0:
            Pot.deposit(auth, pot=pot, account_id=account_id, amount=amount, dedupe_id=os.urandom(16).hex())
        else:
            Pot.withdraw(auth, pot = pot, account_id=account_id, amount=-amount, dedupe_id=os.urandom(16).hex())
    except MonzoGeneralError as e:
        raise Exception(f"Failed to add/remove from pot: {e}")

@app.post('/webhook')
def webhook():
    event = request.json
    print(request.headers)
    if monzo.access_token == '':
        response.status = 200
        return "Warning: No access token found"
    balance = get_main_balance()
    amount_to_move = balance.balance - target_balance
    print(f"Current balance: {balance.balance}")
    move_to_pot(monzo, amount_to_move)
    return "OK"

@app.get('/setup')
def setup():
    return redirect(monzo.authentication_url)

@app.get('/callback')
def callback():
    auth_token = request.query.get('code')
    state_token = request.query.get('state')
    if not auth_token or not state_token:
        response.status = 400
        return "Missing authentication tokens"
    try:
        monzo.authenticate(authorization_token=auth_token, state_token=state_token)
        return "Authentication successful! Please grant permissions in the monzo App. You can close this window."
    except Exception as e:
        response.status = 500
        return f"Authentication failed: {e}"

if __name__ == "__main__":
    run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=True)