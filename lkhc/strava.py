import datetime
import json

from flask import current_app
import requests
import dateutil.parser
import zoneinfo

from lkhc.database import db, Activity, Result, User
import lkhc.user

def webhook():
    current_app.logger.info(f"webhook")

    url = 'https://www.strava.com/api/v3/push_subscriptions'
    response = requests.get(
        url=url,
        params={
            'client_id': current_app.config['STRAVA_CLIENT_ID'],
            'client_secret': current_app.config['STRAVA_CLIENT_SECRET']
        }
    )
    if response.status_code != 200:
        current_app.logger.info(f"Webhook Error:")
        current_app.logger.info(f"{response.text}")
        return None
    
    tokens = response.json()
    current_app.logger.debug(f"webhook get {tokens}")
    
    if tokens:
        return tokens[0]

    current_app.logger.info(f"post")
    response = requests.post(
        url=url,
        data={
            'client_id': current_app.config['STRAVA_CLIENT_ID'],
            'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
            'callback_url':  current_app.config['STRAVA_CALLBACK_URL'],
            'verify_token': current_app.config['STRAVA_VERIFY_TOKEN']
        }
    )
    tokens = response.json()
    current_app.logger.debug(f"request post {tokens}")
    return tokens[0]

def refresh_user(season, id):
    user = db.session.execute(db.select(User).filter_by(season=season,athlete_id=id)).scalar()
    if not user:
        current_app.logger.error(f"missing user {id} in db")
        return

    current_app.logger.info(f"user: {user.firstname} {user.lastname} ({user.athlete_id})")
    current_app.logger.info(f"  db: {datetime.datetime.fromtimestamp(user.expires_at)}, now: {datetime.datetime.now()}")
    if (datetime.datetime.fromtimestamp(user.expires_at) > datetime.datetime.now()):
        return user
        
    response = requests.post(
        url = 'https://www.strava.com/api/v3/oauth/token',
        data = {
            'client_id': current_app.config['STRAVA_CLIENT_ID'],
            'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
            'grant_type': 'refresh_token',
            'refresh_token': user.refresh_token
        }
    )
    tokens = response.json()
    if "errors" in tokens:
        current_app.logger.error(f"Error refreshing token for {id}")
        current_app.logger.error(tokens)
        return None
        
    current_app.logger.info(f"refresh tokens for user {id}")
    user.access_token = tokens['access_token']
    user.refresh_token = tokens['refresh_token']
    user.expires_at = tokens['expires_at']
    lkhc.user.update_user(season, user)
    return user

def check_effort(effort, events):
    "valid effort?"
    for event in events:
        if effort['segment']['id'] == event.segment_id:
            start_utc = dateutil.parser.parse(effort['start_date'])
            local_tz = zoneinfo.ZoneInfo(current_app.config['TIMEZONE'])
            start_local = start_utc.astimezone(local_tz)
            start_date = start_local.date()
            if event.start_date <= start_date <= event.end_date:
                current_app.logger.info(f"effort {effort['id']}, segment {event.segment_id}, {event.start_date} <= {start_date} <= {event.end_date} ✔︎")
                return event
            else:
                current_app.logger.info(f"effort {effort['id']}, segment {event.segment_id}, {event.start_date} <= {start_date} <= {event.end_date} ✘")
    return None

class AnalyzeException(Exception):
    pass

def analyze_activity(season, activity_id, athlete_id, events):
    current_app.logger.info(f"analyze activity {activity_id} {athlete_id}")

    match=False
    user = lkhc.strava.refresh_user(season, athlete_id)
    if not user:
        current_app.logger.error(f"Problem getting athlete {athlete_id}")
        raise AnalyzeException()

    url = f'https://www.strava.com/api/v3/activities/{activity_id}?include_all_efforts=True'
    # url = f'https://www.strava.com/api/v3/activities/9752432636?include_all_efforts=True'
    headers = {
        'Authorization': f"Bearer {user.access_token}"
    }
        
    response = requests.get(
        url=url,
        headers=headers
    )
    # Record Not Found or Resource Not Found if it has been deleted
    if response.status_code != 200:
        current_app.logger.info(f"Error fetching activity")
        current_app.logger.info(f"  {response.text}")
        json = response.json()
        if json['message'] == "Record Not Found" or json['message'] == "Resource Not Found":
            return
        raise AnalyzeException()

    tokens = response.json()  # detailed activity

    if tokens['athlete']['id'] != int(athlete_id):
        current_app.logger.info(f"Sanity check 1 failed.")
        current_app.logger.info(f"  token[athlete][id]: {tokens['athlete']['id']} {type(tokens['athlete']['id'])}")
        current_app.logger.info(f"  athlete_id:         {athlete_id} {type(athlete_id)}")
            
    for effort in tokens['segment_efforts']:
        event = check_effort(effort, events) 
        if not event:
            continue
            
        if effort['athlete']['id'] != int(athlete_id):
            current_app.logger.info(f"Sanity check 2 failed.")
            current_app.logger.info(f"  effort[athlete][id]: {effort['athlete']['id']}")
            current_app.logger.info(f"  athlete_id:          {athlete_id}")
        if effort['activity']['id'] != int(activity_id):
            current_app.logger.info(f"Sanity check 3 failed.")
            current_app.logger.info(f"  effort[activity][id]: {effort['activity']['id']}")
            current_app.logger.info(f"  activity_id:          {activity_id}")
                        
        start_utc = dateutil.parser.parse(effort['start_date'])
        local_tz = zoneinfo.ZoneInfo(current_app.config['TIMEZONE'])
        start_local = start_utc.astimezone(local_tz)
        current_app.logger.info(f"  DEBUG EFFORT: {effort}")
        data = {
                'event_id': event.id,
                'event_seq': event.seq,
                'athlete_id': effort['athlete']['id'],
                'activity_id': effort['activity']['id'],
                'segment_id': effort['segment']['id'],
                'effort_id': effort['id'],
                'start_date': start_local,
                'elapsed_time': effort['elapsed_time'],
                'moving_time': effort['moving_time'],
                'sport_type': tokens['sport_type'],
                'distance': effort['distance'],
                'kom_rank': effort.get('kom_rank', None),
                'pr_rank': effort.get('pr_rank', None)
        }

        lkhc.activity.add_result(season, data)
        match = True

    if not match:
        current_app.logger.info(f"  no matching efforts {activity_id} {athlete_id}")
    return

def purge_activity_WHY(season, activity_id, athlete_id):
    results = db.session.execute(db.select(Result).filter_by(athlete_id=athlete_id, activity_id=activity_id)).scalars()
    
    if results:
        for result in results:
            db.session.delete(result)
            db.session.commit()
        return "Success"

    current_app.logger.info(f"Error: purge activity {season} {activity_id} {athlete_id}")
    return f"Error purging event.\nseason: {season}, activity_id: {activity_id}, athlete_id: {athlete_id}"

ANALYZE_LIMIT = 5
def analyze(season, activityid, athleteid, debug):
    current_app.logger.info(f"analyze starting {season} Activity ID: {activityid} Athlete ID: {athleteid} debug: {debug}")

    error = ""
    
    events = lkhc.database.Event.query.all()
    events = sorted(events, key=lambda event: event.id)

    if activityid:
        analyze_activity(season, activityid, athleteid, events)
        db.session.commit()
    else:
        activities = db.session.execute(db.select(Activity).filter_by(season=season).order_by(Activity.id).limit(ANALYZE_LIMIT)).scalars()

        activities = list(activities)
        
#        for idx, act in enumerate(activities):
#            current_app.logger.info(f"ACT {idx} {act}")
        
        for act in activities:
            # lock activity
            activity = db.session.execute(db.select(Activity).filter_by(id=act.id).with_for_update()).scalar()
            current_app.logger.info(f"ACT {act} {activity}")
            
            if not activity:
                current_app.logger.error(f"Error: unknown activity {act.activity_id}")
                error = error + f"Unknown activity (activity_id: {act.activity_id})\n"
                continue

            if activity.aspect_type in ("create", "update") and activity.object_type == "activity":
                try:
                    analyze_activity(season, activity.object_id, activity.owner_id, events)
                    if not debug:
                        db.session.delete(activity)
                    db.session.commit()
                except AnalyzeException:
                    current_app.logger.error(f"Error: analyze exception {act}")
                    db.session.rollback()

            elif activity.aspect_type == "delete" and activity.object_type == "activity":
                try:
                    #purge_activity(season, activity.object_id, activity.owner_id)
                    if not debug:
                        db.session.delete(activity)
                    db.session.commit()
                except AnalyzeException:
                    db.session.rollback()

            elif activity.aspect_type == "update":
                try:
                    #purge_activity(season, activity.object_id, activity.owner_id)
                    if not debug:
                        db.session.delete(activity)
                    db.session.commit()
                except AnalyzeException:
                    db.session.rollback()

    if error:
        return "Error\n" + error
    return "Success"
