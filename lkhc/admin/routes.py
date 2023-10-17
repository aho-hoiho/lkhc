import datetime
import functools
import operator
import zoneinfo

from flask import render_template, session, request, current_app, url_for, redirect
from lkhc.admin import bp
import lkhc.database
import lkhc.activity
import lkhc.strava


def post():
    password = request.form.get('password')

    copy = {}  # Copy 'werkzeug.datastructures.structures.ImmutableMultiDict'
    for key, value in request.form.items():
        if key == "password":
            value = "XXXXXX"
        copy[key] = value
    current_app.logger.info(f"POST {copy}")

    if request.form.get('logout'):
        session['auth'] = False
        return redirect(url_for('admin.index'))

    if request.form.get('login'):
        if request.form.get('password') == current_app.config['WEB_ADMIN_PASSWORD']:
            current_app.logger.info(f"Admin login from {request.remote_addr}")
            session['auth'] = True
        return redirect(url_for('admin.index'))

    if not session.get('auth', False):
        return render_template('admin-login.html', **params)

    if request.form.get('action') == "add event":
        current_app.logger.info(request.form)
        msg = lkhc.activity.add_event(current_app.config['season'],
                                      request.form)
        return redirect(url_for('admin.index', message=msg))
    if request.form.get('action') == "delete event":
        current_app.logger.info(request.form)
        msg = lkhc.activity.delete_event(current_app.config['season'],
                                         request.form.get("id"),
                                         request.form.get("seq"))
        return redirect(url_for('admin.index', message=msg))
        
    if request.form.get('action') == "export results":
        current_app.logger.info(request.form)
        results = lkhc.activity.export_results(current_app.config['season'],
                                               request.form.get("event"),
                                               request.form.get("type"))
        current_app.logger.info(results)
        return results, 200
        
    if request.form.get('action') == "analyze":
        msg = lkhc.strava.analyze(current_app.config['season'],
                                  request.form.get('activityid'),
                                  request.form.get('athleteid'),
                                  request.form.get('debug'))
        return redirect(url_for('admin.index', message=msg))

    current_app.logger.error(f"POST ACTION {request.form}")
        
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

@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return post()

    webhook = current_app.config.get('webhook', None)
    if not webhook:
        webhook = lkhc.strava.webhook()
        current_app.config['webhook'] = webhook['id']
    
    params = {
        'remote_addr': request.environ.get('REMOTE_ADDR', request.remote_addr),
        'now': str(datetime.datetime.now())
    }
    if not session.get('auth', False):
        return render_template('admin-login.html', **params)

    # ---------------

    raw_message = request.args.get('message', None)
    if raw_message:
        m = raw_message.splitlines()
        message_hdr = m[0]
        message_body = m[1:]
    else:
        message_hdr = None
        message_body = None
    
    # events
    events_db = lkhc.database.Event.query.all()

    events = []
    for event_db in events_db:
        # sort by id + seq
        event = dict((key, getattr(event_db, key)) for key in lkhc.database.event_keys)
        event['segment_id_url'] = f"https://strava.com/segments/{event['segment_id']}"
        event["sort"] = f'{event["id"]:02d}-{event["seq"]:02d}'
        events.append(event)

    events = sorted(events, key=lambda event: event['sort'])

    # users
    users_db = lkhc.database.User.query.all()

    users = []
    for user_db in users_db:
        user = dict((key, getattr(user_db, key)) for key in lkhc.database.user_keys)
        if user['expires_at']:
            user['expires_at'] = datetime.datetime.fromtimestamp(user['expires_at'],
                                                                 zoneinfo.ZoneInfo(current_app.config['TIMEZONE']))
        users.append(user)

    # activities
    activity_urls = [ 'owner_id', 'object_id' ]
    activities_db = lkhc.database.Activity.query.all()

    activities = []
    for activity_db in activities_db:
        activity = dict((key, getattr(activity_db, key)) for key in lkhc.database.activity_keys)
        activity['event_time'] = datetime.datetime.fromtimestamp(activity['event_time'],
                                                                 zoneinfo.ZoneInfo(current_app.config['TIMEZONE']))
        activity['owner_id_url'] = f"https://strava.com/athletes/{activity['owner_id']}"
        activity['object_id_url'] = f"https://strava.com/activities/{activity['object_id']}"
        activities.append(activity)


    # results
    result_urls = [ 'athlete_id', 'activity_id', 'effort_id' ]
    results_db = lkhc.database.Result.query.all()

    results = {}
    for result_db in results_db:
        result = dict((key, getattr(result_db, key)) for key in lkhc.database.result_keys)
        result['athlete_id_url'] = f"https://strava.com/athletes/{result['athlete_id']}"
        result['activity_id_url'] = f"https://strava.com/activities/{result['activity_id']}"
        # result['effort_id_url'] = f"https://strava.com/activities/{result['activity_id']}/segments/{result['effort_id']}"
        result['effort_id_url'] = f"https://strava.com/activities/{result['activity_id']}#{result['effort_id']}"
        if result["event_id"] not in results:
            results[result["event_id"]] = []
        results[result["event_id"]].append(result)

    # unique
    for event_id, event_results in results.items():
        result_dict = functools.reduce(unique_efforts, event_results, {})
        event_results = sorted(result_dict.values(), key=operator.itemgetter("effort_id"))
        results[event_id] = event_results

    result_count = sum([len(res) for res in results.values()])

    # config
    configs_db = lkhc.database.Config.query.all()

    configs = []
    for config_db in configs_db:
        config = dict((key, getattr(config_db, key)) for key in lkhc.database.config_keys)
        configs.append(config)

    params.update( {
        'message_hdr': message_hdr,
        'message_body': message_body,
        'event_keys': lkhc.database.event_keys,
        'events': events,
        'user_keys': lkhc.database.user_keys,
        'users': users,
        'activity_keys': lkhc.database.activity_keys,
        'activity_urls': activity_urls,
        'activities': activities,
        'result_keys': lkhc.database.result_keys,
        'result_urls': result_urls,
        'result_events': sorted(results.keys()),
        'result_count': result_count,
        'results': results,
        'config_keys': lkhc.database.config_keys,
        'configs': configs
    } )

    return render_template('admin-index.html', **params)
