import datetime
import json

from flask import render_template, request, current_app, jsonify, send_file

from lkhc.main import bp
import lkhc.user
import lkhc.activity

@bp.route('/')
def index():
    "home page"
    params = {
        'remote_addr': request.environ.get('REMOTE_ADDR', request.remote_addr),
        'now': str(datetime.datetime.now()),
        'client_id': current_app.config['STRAVA_CLIENT_ID'],
        'redirect_url': current_app.config['STRAVA_OAUTH_REDIRECT_URL']
    }

    return render_template('index.html', **params)

@bp.route('/logo.png')
def logo():
    filename = "static/icon.png"
    return send_file(filename, mimetype='image/png')

@bp.route("/wh", methods=['GET', 'POST'])
def wh():
    if request.method == 'GET':
        mode = request.args.get('hub.mode', '')
        challenge = request.args.get('hub.challenge', '')
        token = request.args.get('hub.verify_token', '')

        current_app.logger.info(f"wh get {mode} {challenge} {token}")
        
        data = {"hub.challenge": challenge}
        return jsonify(data)

    data_str = request.data.decode()
    data = json.loads(data_str)
    lkhc.activity.add_activity(current_app.config['season'],
                               data)
    return "", 200

@bp.route('/strava')
def strava():
    "strava user registration callback"
    params = {
        'remote_addr': request.environ.get('REMOTE_ADDR', request.remote_addr),
        'now': str(datetime.datetime.now()),
        'error': request.args.get('error', ''),
        'state': request.args.get('state', ''),
        'code': request.args.get('code', ''),
        'scope': request.args.get('scope', '')
    }
    current_app.logger.info(f"STRAVA {params['error']} {params['state']} {params['code']} {params['scope']}")
    if params['error']:
        return render_template('strava-error.html', **params)

    user, error = lkhc.user.add_user(current_app.config['season'],
                              params['code'])
    params['user'] = user
    params['message'] = error.get('message', '')
    params['errors'] = error.get('errors', '')
    return render_template('strava.html', **params)
