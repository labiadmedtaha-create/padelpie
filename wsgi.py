import os
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from Padelpie.app import app as padelpie_app, init_db as init_padelpie_db
from Padelpie_Clubs.club_app import app as clubs_app, init_db as init_clubs_db

# Initialise the shared database once when the web process starts.
init_padelpie_db()
init_clubs_db()

# One public service: Padelpie at / and the club portal at /clubs/.
application = DispatcherMiddleware(padelpie_app, {"/clubs": clubs_app})
