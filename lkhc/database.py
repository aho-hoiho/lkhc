import sqlalchemy.exc
from sqlalchemy.dialects.mysql import BIGINT

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

event_keys = ["id", "seq", "name", "segment_id", "start_date", "end_date"]
user_keys = ["athlete_id", "firstname", "lastname", "username", "expires_at",
             "access_token", "refresh_token"]
activity_keys = ["id", "aspect_type", "event_time", "object_id", "object_type",
                 "owner_id", "updates"]
result_keys = ["event_id", "event_seq", "athlete_id", "activity_id", "segment_id",
               "effort_id", "start_date", "elapsed_time", "moving_time", "sport_type",
               "distance", "kom_rank", "pr_rank"]
config_keys = ["key", "value"]

class Config(db.Model):
    key = db.Column(db.String(250), primary_key=True)
    value = db.Column(db.String(250))

    def __repr__(self):
        return f'<Config {self.key} {self.value}>'

class Event(db.Model):
    season = db.Column(db.String(250), primary_key=True)
    id = db.Column(db.Integer, primary_key=True)
    seq = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    segment_id = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    def __repr__(self):
        return f'<Event {self.season}.{self.id}.{self.seq} {self.name} ({self.segment_id})>'
    
class User(db.Model):
    season = db.Column(db.String(250), primary_key=True)
    athlete_id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(250))
    expires_at = db.Column(db.Integer)
    refresh_token = db.Column(db.String(250))
    username = db.Column(db.String(250))
    firstname = db.Column(db.String(250))
    lastname = db.Column(db.String(250))

    def __repr__(self):
        return f'<User {self.firstname} {self.lastname} ({self.athlete_id})>'

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    season = db.Column(db.String(250))
    aspect_type = db.Column(db.String(250))
    event_time = db.Column(db.Integer)
    object_id = db.Column(BIGINT(unsigned=True))
    object_type = db.Column(db.String(250))
    owner_id = db.Column(db.Integer)
    subscription_id = db.Column(db.Integer)
    updates = db.Column(db.String(250))

    def __repr__(self):
        return f'<Activity {self.id} {self.aspect_type} {self.object_id} {self.object_type} ({self.owner_id})>'

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    season = db.Column(db.String(250))
    event_id = db.Column(db.Integer)
    event_seq = db.Column(db.Integer)
    athlete_id = db.Column(db.Integer)
    activity_id = db.Column(BIGINT(unsigned=True))
    segment_id = db.Column(BIGINT(unsigned=True))
    effort_id = db.Column(BIGINT(unsigned=True))
    start_date = db.Column(db.DateTime)
    elapsed_time = db.Column(db.Integer)
    moving_time = db.Column(db.Integer)
    sport_type = db.Column(db.String(250))
    distance = db.Column(db.Float)
    kom_rank = db.Column(db.Integer)
    pr_rank = db.Column(db.Integer)

    def __repr__(self):
        return f'<Result {self.id} {self.event_id} {self.effort_id} ({self.athlete_id})>'
    
def season():
    try:
        cfg = db.session.execute(db.select(Config).filter_by(key="season")).scalar()
        if not season:
            current_app.logger.error("Configuration error: No 'season' defined in database.")
    except sqlalchemy.exc.ProgrammingError as exc:
        current_app.logger.error(f"Configuration error: {exc}")
        return None

    return "2023"
    return cfg.value

