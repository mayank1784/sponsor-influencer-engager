from app import app, db
from app.models import User, Campaign, AdRequest

with app.app_context():
    db.create_all()
print("Database initialized.")
