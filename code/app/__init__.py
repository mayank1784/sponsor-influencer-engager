from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Api


app = Flask(__name__, template_folder="templates")
app.config.from_object('config.Config')

db = SQLAlchemy(app)
api = Api(app)
@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt='%Y-%m-%d'):
    return date.strftime(fmt)

from app import routes, models, api_resources

