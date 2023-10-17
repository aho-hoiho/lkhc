import datetime
import functools
import operator

from flask import current_app
import flask_excel as excel
import sqlalchemy.exc

from lkhc.database import db, Activity, Event, Result, User, result_keys

def add_event(season, data):
    current_app.logger.info(f"ADD EVENT {season} {data}")

    event = Event(
        season = season,
        id = data['id'],
        seq = data['seq'] if data['seq'] else 0,
        name = data['name'],
        segment_id = data['segment_id'],
        start_date = data['start_date'],
        end_date = data['end_date'],
    )
    try:
        db.session.add(event)
        db.session.commit()
        return "Success"
    except sqlalchemy.exc.IntegrityError as e:
        current_app.logger.info(f"Error: add event {e}")
        return f"Error adding event.\n{e}"

def delete_event(season, id, seq):
    current_app.logger.info(f"DELETE EVENT {season} {id} {seq}")
    event = db.session.execute(db.select(Event).filter_by(season=season,id=id,seq=seq)).scalar()
    if not event:
        current_app.logger.info(f"Error: delete event {season} {id} {seq}")
        return f"Error deleting event.\nseason: {season}, event_id: {id}, seq: {seq}"
    else:
        db.session.delete(event)
        db.session.commit()
        return "Success"

def add_result(season, data):
    current_app.logger.info(f"ADD RESULT {season} {data}")

    result = Result(
        season = season,
        event_id = data['event_id'],
        event_seq = data['event_seq'],
        athlete_id = data['athlete_id'],
        activity_id = data['activity_id'],
        segment_id = data['segment_id'],
        effort_id = data['effort_id'],
        start_date = data['start_date'],
        elapsed_time = data['elapsed_time'],
        moving_time = data['moving_time'],
        sport_type = data['sport_type'],
        distance = data['distance'],
        kom_rank = data['kom_rank'],
        pr_rank = data['pr_rank'],
    )
    db.session.add(result)

def add_activity(season, data):
    current_app.logger.info(f"ADD ACTIVITY {season} {data}")

    activity = Activity(
        season = season,
        aspect_type = data['aspect_type'],
        event_time = data['event_time'],
        object_id = data['object_id'],
        object_type = data['object_type'],
        owner_id = data['owner_id'],
        subscription_id = data['subscription_id'],
        updates = str(data['updates']) if data['updates'] else None,
    )
    db.session.add(activity)
    db.session.commit()
        
def unique_efforts(accum, element):
    if element['effort_id'] in accum:
        old = accum[element['effort_id']]
        if( element['activity_id'] != old['activity_id'] or
            element['elapsed_time'] != old['elapsed_time'] ):
            print("Error: data mismatch")
            print(old)
            print(element)
    else:
        accum[element['effort_id']] = element
    return accum
    
def export_results(season, event, type_):
    current_app.logger.info(f"EXPORT RESULTS {season} {event} {type_}")

    excel.init_excel(current_app)
    export_keys = ['event_id', 'event_seq', 'username', 'firstname', 'lastname',
                   'athlete_id', 'activity_id', 'segment_id', 'effort_id', 'start_date', 'start_time',
                   'elapsed_time', 'moving_time', 'elapsed_time_sec', 'moving_time_sec',
                   'distance_km', 'distance', 'sport_type', 'kom_rank', 'pr_rank']

    data = []
    data.append( export_keys )
    results_db = db.session.execute(db.select(Result).filter_by(season=season,
                                                                event_id=int(event))).scalars()
    results = [ dict((key, getattr(result_db, key)) for key in result_keys) for result_db in results_db ]

    if type_ == "unique":
        result_dict = functools.reduce(unique_efforts, results, {})
        results = sorted(result_dict.values(), key=operator.itemgetter("effort_id"))
    elif type_ == "all":
        pass
    else:
        current_app.logger.error(f"Error. Unknown export type: '{type_}'.")
        return
    
    for result in results:
        user = db.session.execute(db.select(User).filter_by(season=season,athlete_id=result['athlete_id'])).scalar()
        if not user:
            current_app.logger.error(f"missing user {id} in db")
            continue

        result['username'] = user.username
        result['firstname'] = user.firstname
        result['lastname'] = user.lastname
        result['sequence'] = result['event_seq']
        result['start_time'] = result['start_date'].time()
        result['start_date'] = result['start_date'].date()
        result['elapsed_time_sec'] = result['elapsed_time']
        result['moving_time_sec'] = result['moving_time']
        result['elapsed_time'] = str(datetime.timedelta(seconds=result['elapsed_time']))
        result['moving_time'] = str(datetime.timedelta(seconds=result['moving_time']))
        result['distance_km'] = f"{float(result['distance']) / 1000:0.3f}"
        result['distance'] = f"{float(result['distance']) * 0.621371 / 1000:0.3f}"

        xls = [result.get(key) for key in export_keys]
        data.append( xls )

    response = excel.make_response_from_array(data, "csv",
                                              file_name=f"results-{season}-{event}.csv")

    # Compute Statistics
    day = {}
    kom = {}
    pr = {}
    for result in results:
        if result['start_date'] not in day:
            day[result['start_date']] = 0
        day[result['start_date']] = day[result['start_date']] + 1

        if result['kom_rank']:
            if result['kom_rank'] not in kom:
                kom[result['kom_rank']] = 0
            kom[result['kom_rank']] = kom[result['kom_rank']] + 1

        if result['pr_rank']:
            if result['pr_rank'] not in pr:
                pr[result['pr_rank']] = 0
            pr[result['pr_rank']] = pr[result['pr_rank']] + 1

    current_app.logger.info(f"Statistics")
    current_app.logger.info(f"∙ Start date: {day}")
    current_app.logger.info(f"∙ KOM: {kom}")
    current_app.logger.info(f"∙ PR: {pr}")

    return response

