from flask import current_app
import requests
import sqlalchemy.exc

from lkhc.database import db, User

def add_user(season, code):
    current_app.logger.info(f"ADD USER {code}")
    response = requests.post(
        url = 'https://www.strava.com/api/v3/oauth/token',
        data = {
            'client_id': current_app.config['STRAVA_CLIENT_ID'],
            'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
            'code': code,
            'grant_type': 'authorization_code'
        }
    )
    tokens = response.json()
    if tokens.get('errors', False):
        current_app.logger.error(f"OAUTH ERROR")
        current_app.logger.error(f"{tokens}")
        return None, tokens
        
    user = db.session.execute(db.select(User).filter_by(season=season,athlete_id=tokens['athlete']['id'])).scalar()
    if user: # update
        current_app.logger.info(f"update user: original {user}")
        user.access_token = tokens['access_token']
        user.expires_at = tokens['expires_at']
        user.refresh_token = tokens['refresh_token']
        user.username = tokens['athlete']['username']
        user.firstname = tokens['athlete']['firstname']
        user.lastname = tokens['athlete']['lastname']
        current_app.logger.info(f"update user: new {user}")
        db.session.commit()
    else: # insert
        user = User(
            season=season,
            athlete_id= tokens['athlete']['id'],
            access_token= tokens['access_token'],
            expires_at= tokens['expires_at'],
            refresh_token= tokens['refresh_token'],
            username= tokens['athlete']['username'],
            firstname= tokens['athlete']['firstname'],
            lastname= tokens['athlete']['lastname']
        )
        db.session.add(user)
        db.session.commit()
        current_app.logger.info(f"insert user {user}")
                    
    return user, {}

def update_user(season, user):
    db.session.add(user)
    db.session.commit()
    # current_app.logger.info(f"UPDATE {user}")

