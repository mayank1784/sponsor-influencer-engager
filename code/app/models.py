from datetime import datetime
from app import db
import enum
from sqlalchemy import Enum


class AdRequestStatus(enum.Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    NEGOTIATING = "Negotiating"
    COMPLETED = "Completed"
    ABANDONED = "Abandoned"
    
class Visibility(enum.Enum):
    PRIVATE='Private'
    PUBLIC='Public'
    
class CampaignStatus(enum.Enum):
    COMPLETED = 'Completed'
    ONGOING = 'Ongoing'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(64))
    flagged = db.Column(db.Boolean, default=False)

class Sponsor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    company_name = db.Column(db.String(140))
    industry = db.Column(db.String(140))
    budget = db.Column(db.Float)
    user = db.relationship('User', backref=db.backref('sponsor_profile', uselist=False))
    campaigns = db.relationship('Campaign', backref='sponsor', lazy='dynamic')

class Influencer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    insta_profile_url = db.Column(db.String(256))
    category = db.Column(db.String(140))
    followers = db.Column(db.Integer)
    niche = db.Column(db.String(140))
    reach = db.Column(db.Integer)
    user = db.relationship('User', backref=db.backref('influencer_profile', uselist=False))
    ad_requests = db.relationship('AdRequest', back_populates='influencer')

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140))
    description = db.Column(db.String(500))
    niche = db.Column(db.String(100))
    start_date = db.Column(db.DateTime, index=True, default=datetime.now())
    end_date = db.Column(db.DateTime)
    budget = db.Column(db.Float)
    visibility = db.Column(Enum(Visibility), default=Visibility.PRIVATE)
    goals = db.Column(db.String(500))
    status = db.Column(Enum(CampaignStatus), default=CampaignStatus.ONGOING)
    sponsor_id = db.Column(db.Integer, db.ForeignKey('sponsor.id'))
    ad_requests = db.relationship('AdRequest', back_populates='campaign')

class AdRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    influencer_id = db.Column(db.Integer, db.ForeignKey('influencer.id'))
    messages = db.Column(db.String(500))
    requirements = db.Column(db.String(500))
    payment_amount = db.Column(db.Float)
    status = db.Column(Enum(AdRequestStatus), default=AdRequestStatus.PENDING)
    campaign = db.relationship('Campaign', back_populates='ad_requests')
    influencer = db.relationship('Influencer', back_populates='ad_requests')