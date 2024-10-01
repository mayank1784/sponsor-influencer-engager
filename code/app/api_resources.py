from flask_restful import Resource, fields, marshal_with, reqparse, abort, request
from sqlalchemy import not_
from app import api, db, app
from app.models import User, Campaign, AdRequest, Influencer, Visibility, CampaignStatus, AdRequestStatus
from app.decorators import login_required
from datetime import datetime



# Define the resource fields
user_fields = {
    'id': fields.Integer,
    'username': fields.String,
    'email': fields.String,
    'role': fields.String,
}

campaign_fields = {
    'id': fields.Integer,
    'name': fields.String,
    'description': fields.String,
    'niche': fields.String,
    'start_date': fields.DateTime,
    'end_date': fields.DateTime,
    'budget': fields.Float,
    'visibility': fields.String,
    'goals': fields.String,
    'status': fields.String,
    'sponsor_id': fields.Integer,
}


ad_request_fields = {
    'id': fields.Integer,
    'campaign_id': fields.Integer,
    'influencer_id': fields.Integer,
    'messages': fields.String,
    'requirements': fields.String,
    'payment_amount': fields.Float,
    'status': fields.String
}

influencer_fields = {
    'id': fields.Integer,
    'user_id': fields.Integer,
    'insta_profile_url': fields.String,
    'category': fields.String,
    'niche': fields.String,
    'reach': fields.Integer,
    'followers': fields.Integer,
    'username': fields.String(attribute=lambda x: x.user.username),
    'ad_requests': fields.List(fields.Nested(ad_request_fields))
    
}

sponsor_fields = {
    'id': fields.Integer,
    'user_id': fields.Integer,
    'company_name': fields.String,
    'industry': fields.String,
    'budget': fields.Float
}

message_fields = {
    'message': fields.String
}


# Custom error handler for 500
@app.errorhandler(500)
def internal_error(error):
    return {'message': 'Internal server error'}, 500

class UserAPI(Resource):
    @login_required
    @marshal_with(user_fields)
    def get(self, user_id):
        try:
            user = User.query.get(user_id)
            if not user:
                return {'error': 'User not found'}, 404
            return user,200
        except Exception as e:
            abort(500, message=str(e))

class CompleteCampaign(Resource):
    def put(self, campaign_id):
        # Fetch the campaign by ID
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            abort(404, message="Campaign not found")

        # Update campaign status
        campaign.status = CampaignStatus.COMPLETED

        # Update related ad requests
        ad_requests = AdRequest.query.filter(AdRequest.campaign_id == campaign_id,
                                            AdRequest.status != AdRequestStatus.COMPLETED , AdRequest.status != AdRequestStatus.REJECTED).all()
        for ad_request in ad_requests:
            ad_request.status = AdRequestStatus.ABANDONED

        try:
            db.session.commit()
            return {'message': 'Campaign completed and ad requests updated'}, 200
        except Exception as e:
            db.session.rollback()
            abort(500, message=str(e))
            
class CampaignAPI(Resource):
    @marshal_with(campaign_fields)
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True)
        parser.add_argument('description', type=str, required=True)
        parser.add_argument('start_date', type=lambda x: datetime.strptime(x, '%Y-%m-%d'), required=True)
        parser.add_argument('end_date', type=lambda x: datetime.strptime(x, '%Y-%m-%d'), required=True)
        parser.add_argument('budget', type=float, required=True)
        parser.add_argument('visibility', type=str, required=True)
        parser.add_argument('goals', type=str, required=True)
        parser.add_argument('niche', type=str, required=True)
        parser.add_argument('sponsor_id', type=int, required=True)
        args = parser.parse_args()
        try:
            campaign = Campaign(
                name=args['name'],
                description=args['description'],
                start_date=args['start_date'],
                end_date=args['end_date'],
                budget=args['budget'],
                niche = args['niche'],
                visibility=Visibility[args['visibility'].upper()],
                goals=args['goals'],
                sponsor_id=args['sponsor_id']
            )
            db.session.add(campaign)
            db.session.commit()
            return campaign, 201
        except Exception as e:
            db.session.rollback()
            abort(500, message=str(e))
                
    @marshal_with(campaign_fields)
    def get(self, campaign_id=None):
        if campaign_id:
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                abort(404, message='Campaign not found')
            return campaign, 200
        else:
            parser = reqparse.RequestParser()
            parser.add_argument('sponsor_id', type=int, required=False)
            args = parser.parse_args()

            if args['sponsor_id']:
                campaigns = Campaign.query.filter_by(sponsor_id=args['sponsor_id']).all()
                return campaigns, 200
            else:
                campaigns = Campaign.query.all()
            return campaigns, 200
                
    def delete(self, campaign_id):
        try:
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                abort(404, message="Campaign not found")
            ad_requests = AdRequest.query.filter_by(campaign_id=campaign_id).all()
            for ad_request in ad_requests:
                if (ad_request.status != AdRequestStatus.COMPLETED or ad_request.status != AdRequestStatus.REJECTED):
                    ad_request.status = AdRequestStatus.ABANDONED
            db.session.commit()
            db.session.delete(campaign)
            db.session.commit()
            return {'message': 'Campaign deleted successfully'}, 200
        except Exception as e:
            db.session.rollback()
            abort(500, message=str(e))
            
            
class AdRequestAPI(Resource):
    @marshal_with(ad_request_fields)
    def get(self, ad_request_id):
        ad_request = AdRequest.query.get(ad_request_id)
        if not ad_request:
            return {'error': 'Ad request not found'}, 404
        return ad_request
    
    
    @marshal_with(ad_request_fields)
    def post(self):
       
        parser = reqparse.RequestParser()
        parser.add_argument('campaign_id', type=int, required=True)
        parser.add_argument('influencer_id', type=int, required=True)
        parser.add_argument('messages', type=str, required=True)
        parser.add_argument('requirements', type=str, required=True)
        parser.add_argument('payment_amount', type=float, required=True)
        args = parser.parse_args()
        try:
            campaign = Campaign.query.get(args['campaign_id'])
            
            if not campaign:
                abort(404, message="Campaign not found")
                
            if campaign.status == CampaignStatus.COMPLETED:
                abort(400, message="Cannot create ad request for a completed campaign")
            existing_ad_request = AdRequest.query.filter_by(
            campaign_id=args['campaign_id'], 
            influencer_id=args['influencer_id']).filter(
            not_(AdRequest.status.in_([AdRequestStatus.COMPLETED, AdRequestStatus.REJECTED]))).first()

            if existing_ad_request:
                abort(400, message="Ad request for this campaign and influencer already exists")
                

            ad_request = AdRequest(
                campaign_id=args['campaign_id'],
                influencer_id=args['influencer_id'],
                messages=args['messages'],
                requirements=args['requirements'],
                payment_amount=args['payment_amount'],
            )
            db.session.add(ad_request)
            db.session.commit()
            return ad_request, 201
        except Exception as e:
            db.session.rollback()
            abort(500, message='An internal error occured or the ad request already existed')    
    
    @marshal_with(ad_request_fields)
    def patch(self, ad_request_id):
        try:
            ad_request = AdRequest.query.get(ad_request_id)
            if not ad_request:
                abort(404, message="Ad request not found")

            request_data = request.json
            for key, value in request_data.items():
                if hasattr(ad_request, key):
                    setattr(ad_request, key, value)

            db.session.commit()
            return ad_request, 200
        except Exception as e:
            db.session.rollback()
            abort(500, message=str(e))
    
    
    def delete(self, ad_request_id):
        try:
            ad_request = AdRequest.query.get(ad_request_id)
            if not ad_request:
                abort(404, message="Ad request not found")
            db.session.delete(ad_request)
            db.session.commit()
            return {'message': 'Ad request deleted successfully'}, 200
        except Exception as e:
            abort(500, message=str(e))
            
    
# Search for influencers and campaigns
class SearchInfluencersAPI(Resource):
    @marshal_with(influencer_fields)
    def get(self, influencer_id=None):
        try:
            if influencer_id is not None:
                # Search by influencer_id
                influencer = Influencer.query.get(influencer_id)
                if not influencer:
                    return {"message": "Influencer not found"}, 404
                return influencer, 200
            
            # Search by other criteria
            name = request.args.get('name')
            niche = request.args.get('niche')
            followers = request.args.get('followers')

            # Example filtering logic
            query = Influencer.query.join(User)

            if name:
                query = query.filter(User.username.ilike(f"%{name}%"))

            if niche:
                query = query.filter(Influencer.niche.ilike(f"%{niche}%"))

            if followers:
                query = query.filter(Influencer.followers >= int(followers))

            influencers = query.all()
            
            return influencers, 200

        except Exception as e:
            print(f"Error processing request: {str(e)}")
            return {"message": "Error processing request"}, 400




api.add_resource(UserAPI, '/api/users/<int:user_id>')
api.add_resource(CompleteCampaign, '/api/campaigns/<int:campaign_id>/complete')
api.add_resource(CampaignAPI, '/api/campaigns', '/api/campaigns/<int:campaign_id>')
api.add_resource(AdRequestAPI, '/api/ad_requests', '/api/ad_requests/<int:ad_request_id>')
api.add_resource(SearchInfluencersAPI, '/api/search/influencers', '/api/search/influencers/<int:influencer_id>')
