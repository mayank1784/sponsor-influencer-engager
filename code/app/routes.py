from flask import render_template, flash, redirect, url_for, request, session
from datetime import datetime, timedelta
from sqlalchemy import func
import requests
from collections import Counter, defaultdict
from sqlalchemy.orm import aliased
from datetime import datetime
from app import app, db
from sqlalchemy import desc, and_, exists
from sqlalchemy.exc import IntegrityError
from app.models import User, Campaign, AdRequest, Sponsor, Influencer, AdRequestStatus, CampaignStatus
from werkzeug.security import generate_password_hash, check_password_hash
from app.decorators import login_required, roles_required
from app.models import Visibility
from app.utils import scrape_data, complete_old_campaigns, calculate_reach

def get_date_range(date):
    # Define ranges
    if 1 <= date.day <= 7:
        return f"{date.year}-{date.month:02d}-01 to {date.year}-{date.month:02d}-07"
    elif 8 <= date.day <= 14:
        return f"{date.year}-{date.month:02d}-08 to {date.year}-{date.month:02d}-14"
    elif 15 <= date.day <= 21:
        return f"{date.year}-{date.month:02d}-15 to {date.year}-{date.month:02d}-21"
    elif 22 <= date.day <= 28:
        return f"{date.year}-{date.month:02d}-22 to {date.year}-{date.month:02d}-28"
    else:
        last_day = (date.replace(month=date.month % 12 + 1, day=1) - timedelta(days=1)).day
        return f"{date.year}-{date.month:02d}-29 to {date.year}-{date.month:02d}-{last_day:02d}"


#====================================================== Home Routes =======================================================
@app.route('/')
@app.route('/index')
def index():
    complete_old_campaigns()
    return render_template('index.html')

# User Registration and Profile Management
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Validate form inputs
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if not username or not email or not password or not role:
            flash('Please fill out all required fields.')
            return render_template('register.html', title='Register')

        hashed_password = generate_password_hash(password)

        try:
            new_user = User(username=username, email=email, password_hash=hashed_password, role=role)
            db.session.add(new_user)
            db.session.flush()  # To Ensure new_user.id is available

            if role == 'sponsor':
                company_name = request.form.get('company_name')
                industry = request.form.get('industry')
                budget = request.form.get('budget')

                if not company_name or not industry or not budget:
                    flash('Please fill out all sponsor fields.')
                    return render_template('register.html', title='Register')

                try:
                    budget = float(budget)
                except ValueError:
                    flash('Budget must be a number.')
                    return render_template('register.html', title='Register')

                new_sponsor = Sponsor(user_id=new_user.id, company_name=company_name, industry=industry, budget=budget)
                db.session.add(new_sponsor)

            elif role == 'influencer':
                insta_profile_url = request.form.get('insta_profile_url')
                category = request.form.get('category')
                niche = request.form.get('niche')

                if not insta_profile_url or not category or not niche:
                    flash('Please fill out all influencer fields.')
                    return render_template('register.html', title='Register')

                followers = scrape_data(insta_profile_url.split('/')[-1])

                new_influencer = Influencer(user_id=new_user.id, insta_profile_url=insta_profile_url, category=category, niche=niche, followers=followers)
                db.session.add(new_influencer)

            db.session.commit()
            flash('Registration successful!')
            return redirect(url_for('login'))

        except IntegrityError:
            db.session.rollback()
            flash('Username or email already exists.')
            return render_template('register.html', title='Register')
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}")
            return render_template('register.html', title='Register')

    elif request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('register.html', title='Register')


@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        return render_template('admin/admin_profile.html', user=user)
    elif user.role == 'sponsor':
        sponsor = Sponsor.query.filter_by(user_id=user.id).first()
        return render_template('sponsor/sponsor_profile.html', user=user, sponsor=sponsor)
    elif user.role == 'influencer':
        influencer = Influencer.query.filter_by(user_id=user.id).first()
        calculate_reach(influencer.id)
        return render_template('influencer/influencer_profile.html', user=user, influencer=influencer)
    else:
        return redirect(url_for('index'))

    
@app.route('/edit_profile/sponsor/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_required('sponsor')
def edit_sponsor_profile(user_id):
    sponsor = Sponsor.query.filter_by(user_id=user_id).first_or_404()
    if request.method == 'POST':
        try:
            # Update fields if they are provided in the form
            sponsor.company_name = request.form.get('company_name', sponsor.company_name)
            sponsor.industry = request.form.get('industry', sponsor.industry)
            
            budget = request.form.get('budget')
            if budget:
                sponsor.budget = float(budget)

            db.session.commit()
            flash('Sponsor information updated successfully!')
            return redirect(url_for('profile',user_id=user_id))  # Redirect to some route after successful update
        except ValueError:
            flash('Budget must be a number.')
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}")

    return render_template('sponsor/edit_sponsor_profile.html', sponsor=sponsor)


@app.route('/edit_profile/influencer/<int:user_id>', methods=['GET', 'POST'])
@login_required
@roles_required('influencer')
def edit_influencer_profile(user_id):
    influencer = Influencer.query.filter_by(user_id=user_id).first_or_404()
    calculate_reach(influencer.id)
    if request.method == 'POST':
        insta_url = request.form.get('insta_profile_url')
        followers = scrape_data(insta_url.split('/')[-1])
        influencer.insta_profile_url = request.form.get('insta_profile_url',influencer.insta_profile_url)
        influencer.category = request.form.get('category', influencer.category)
        influencer.niche = request.form.get('niche', influencer.niche)
        influencer.followers = followers
        
        db.session.commit()
        flash('Profile updated successfully.')
        return redirect(url_for('profile', user_id=user_id))
    return render_template('influencer/edit_influencer_profile.html', influencer=influencer)


#====================================================== User Session Management====================================================== 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['role'] = user.role
                role = session['role']
                return redirect(url_for(f'{role}_dashboard', user_id = session['user_id']))
            else:
                flash('Invalid username or password')
        except Exception as e:
            flash(f"error: {e}")
    return render_template('login.html', title='Sign In')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('index'))


#====================================================== Dashboard Management ====================================================== 
@app.route('/sponsor/dashboard/<int:user_id>')
@login_required
@roles_required('admin','sponsor')
def sponsor_dashboard(user_id):
    complete_old_campaigns()
    campaigns_progress_data = []
    ad_status_data = {
        'Pending': 0,
        'Accepted': 0,
        'Negotiating': 0,
        'Rejected': 0,
        'Completed': 0,
        'Abandoned': 0
    }
    campaign_status = {
        'Private/Completed': 0,
        'Private/Ongoing': 0,
        'Public/Completed': 0,
        'Public/Ongoing': 0
    }
    influencer_ad_counts = {}
    try:
        admin=False
        role = session['role']
        if role=='admin':
            admin = True
        sponsor = Sponsor.query.filter_by(user_id=user_id).first()
        if not sponsor:
            flash("Sponsor not found.")
            return redirect(url_for('index'))

        
        campaigns = Campaign.query.filter(Campaign.sponsor_id == sponsor.id)
        ad_status_counts = Counter()
        campaign_status_counts = Counter()
        
        for campaign in sponsor.campaigns:
            for ad in campaign.ad_requests:
                ad_status_counts[ad.status] += 1
            
                 # Count ad requests served by each influencer
                if ad.status in [AdRequestStatus.ACCEPTED, AdRequestStatus.COMPLETED]:
                    influencer_id = ad.influencer_id
                    if influencer_id not in influencer_ad_counts:
                        influencer_ad_counts[influencer_id] = {
                            'influencer': ad.influencer,
                            'ad_request_count': 0
                        }
                    influencer_ad_counts[influencer_id]['ad_request_count'] += 1
                    
                
            if campaign.status == CampaignStatus.COMPLETED:
                if campaign.visibility == Visibility.PRIVATE:
                    campaign_status_counts['Private/Completed'] += 1
                else:
                    campaign_status_counts['Public/Completed'] += 1
                progress = 100
            else:
                if campaign.visibility == Visibility.PRIVATE:
                    campaign_status_counts['Private/Ongoing'] += 1
                else:
                    campaign_status_counts['Public/Ongoing'] += 1
                total_requests = AdRequest.query.filter(
                    and_(
                        AdRequest.campaign_id == campaign.id,
                        AdRequest.status.in_([
                            AdRequestStatus.COMPLETED,
                            AdRequestStatus.NEGOTIATING,
                            AdRequestStatus.PENDING,
                            AdRequestStatus.ACCEPTED
                        ])
                    )
                ).count()

                completed_requests = AdRequest.query.filter(
                    and_(
                        AdRequest.campaign_id == campaign.id,
                        AdRequest.status == AdRequestStatus.COMPLETED
                    )
                ).count()
                if total_requests > 0:
                    progress = (completed_requests / total_requests) * 100
                    progress = round(progress, 2)
                else:
                    progress = 0.00

             # Convert campaign to a dictionary and add ad requests
            campaign_data = campaign.__dict__.copy()
            campaign_data['progress'] = progress  # Append the progress value
            
            campaigns_progress_data.append(campaign_data)
          
            ad_status_data = {
                'Pending': ad_status_counts.get(AdRequestStatus.PENDING,0),
                'Accepted': ad_status_counts.get(AdRequestStatus.ACCEPTED,0),
                'Negotiating': ad_status_counts.get(AdRequestStatus.NEGOTIATING,0),
                'Rejected': ad_status_counts.get(AdRequestStatus.REJECTED,0),
                'Completed': ad_status_counts.get(AdRequestStatus.COMPLETED,0),
                'Abandoned': ad_status_counts.get(AdRequestStatus.ABANDONED,0)
            
            }
            campaign_status = {
                'Private/Completed':campaign_status_counts.get('Private/Completed', 0),
                'Private/Ongoing':campaign_status_counts.get('Private/Ongoing', 0),
                'Public/Completed':campaign_status_counts.get('Public/Completed', 0),
                'Public/Ongoing':campaign_status_counts.get('Public/Ongoing', 0)
            }
            
            # Sort influencers by ad request count in descending order
        sorted_influencers = sorted(influencer_ad_counts.values(),
                                    key=lambda x: x['ad_request_count'], reverse=True)
      
        return render_template('sponsor/sponsor_dashboard.html',
                               campaigns=campaigns,
                               campaigns_progress=campaigns_progress_data,
                               sponsor=sponsor, ad_status_data = ad_status_data,
                               campaign_status = campaign_status,
                               sponsors_influencers=sorted_influencers,
                               admin=admin)
    except Exception as e:
        flash(f'Error: {str(e)}')
    return redirect(url_for('index'))


@app.route('/influencer/dashboard/<int:user_id>')
@login_required
@roles_required('admin','influencer')
def influencer_dashboard(user_id):
   
    complete_old_campaigns()
     # Initialize statistics
    influencer_stats = {
            'total_ad_requests': 0,
            'accepted_ad_requests': 0,
            'completed_ad_requests': 0,
            'rejected_ad_requests': 0,
            'pending_ad_requests': 0,
            'negotiating_ad_requests': 0,
            'payments_recieved': 0,
            'upcoming_payments':0,
            'average_earning': 0,
        }
    admin = False

    try:
        if session['role']=='admin':
            admin=True
        # Fetch the influencer by user_id
        influencer = Influencer.query.filter_by(user_id=user_id).first()
        calculate_reach(influencer.id)
        if not influencer:
            flash("Influencer not found.")
            return redirect(url_for('index'))

       

        # Fetch all ad requests for the influencer
        ad_requests = AdRequest.query.filter_by(influencer_id=influencer.id).all()
        completed_accepted_ads = [ad for ad in ad_requests if ad.status in [AdRequestStatus.COMPLETED, AdRequestStatus.ACCEPTED]]
        
        # Calculate the sum of payments for completed ad requests
        completed_payment_sum = sum(ad.payment_amount for ad in ad_requests if ad.status == AdRequestStatus.COMPLETED)
        # Calculate the upcoming payments
        upcoming_payment = sum(ad.payment_amount for ad in ad_requests if ad.status == AdRequestStatus.ACCEPTED)
        
        average_earing=0
        try:
            average_earing = (completed_payment_sum + upcoming_payment) / len(completed_accepted_ads)
        except Exception as e:
            pass
        
        one_week_from_now = datetime.now() + timedelta(days=7)

        # Filter ad requests with status ACCEPTED and campaign deadline within the next week
        deadline_approaching_ads = [ad for ad in ad_requests
            if ad.status == AdRequestStatus.ACCEPTED and ad.campaign.end_date <= one_week_from_now]
        
        influencer_stats['payments_recieved'] = completed_payment_sum
        influencer_stats['upcoming_payments'] = upcoming_payment
        influencer_stats['average_earning'] = average_earing
        influencer_stats['total_ad_requests'] = len(ad_requests)

        # Calculate ad request status counts
        ad_status_counts = Counter(ad.status for ad in ad_requests)
        influencer_stats['accepted_ad_requests'] = ad_status_counts.get(AdRequestStatus.ACCEPTED, 0)
        influencer_stats['completed_ad_requests'] = ad_status_counts.get(AdRequestStatus.COMPLETED, 0)
        influencer_stats['rejected_ad_requests'] = ad_status_counts.get(AdRequestStatus.REJECTED, 0)
        influencer_stats['pending_ad_requests'] = ad_status_counts.get(AdRequestStatus.PENDING, 0)
        influencer_stats['negotiating_ad_requests'] = ad_status_counts.get(AdRequestStatus.NEGOTIATING, 0)

        ad_status_data = {
            'Pending': influencer_stats['pending_ad_requests'],
            'Accepted': influencer_stats['accepted_ad_requests'],
            'Negotiating': influencer_stats['negotiating_ad_requests'],
            'Rejected': influencer_stats['rejected_ad_requests'],
            'Completed': influencer_stats['completed_ad_requests']
        }
        
        
        # Organize data for the bar chart
        campaign_participation = defaultdict(lambda: defaultdict(int))
        for ad_request in ad_requests:
            date_range = get_date_range(ad_request.campaign.start_date)
            campaign_participation[date_range][ad_request.status.value] += 1

        # Convert to a list of dictionaries for easier handling in the template
        campaign_participation_data = [
            {'date_range': date_range, **statuses} for date_range, statuses in campaign_participation.items()
        ]
        
        return render_template('influencer/influencer_dashboard.html',
                               influencer=influencer,
                               influencer_stats=influencer_stats,
                               ad_status_data=ad_status_data,
                               deadline_approaching_ads = deadline_approaching_ads,
                               campaign_participation_data=campaign_participation_data,
                               admin=admin)
    except Exception as e:
        flash(f'Error: {str(e)}')
    return redirect(url_for('index'))

@app.route('/admin/dashboard/<int:user_id>')
@login_required
@roles_required('admin')
def admin_dashboard(user_id):
    complete_old_campaigns()
    try:
        # Fetch all sponsors and their campaigns
        sponsors = Sponsor.query.all()

        # Prepare a list to hold sponsors and their campaign counts
        sponsor_campaign_counts = []

        # Iterate through sponsors and count campaigns
        for sponsor in sponsors:
            campaigns_count = sum(
                1 for campaign in sponsor.campaigns
            )
            sponsor_campaign_counts.append({
                'sponsor': sponsor,
                'campaign_count': campaigns_count
            })

        # Sort by campaign count and get the top 5
        top_sponsors = sorted(sponsor_campaign_counts, key=lambda x: x['campaign_count'], reverse=True)[:5]

        # Fetch all influencers and their ad requests
        influencers = Influencer.query.all()

        # Prepare a list to hold influencers and their ad request counts
        influencer_ad_request_counts = []

        # Iterate through influencers and count valid ad requests
        for influencer in influencers:
            valid_ad_requests_count = sum(
                1 for ad_request in influencer.ad_requests
                if ad_request.status not in [AdRequestStatus.REJECTED, AdRequestStatus.ABANDONED]
            )
            influencer_ad_request_counts.append({
                'influencer': influencer,
                'ad_request_count': valid_ad_requests_count
            })

        # Sort by ad request count and get the top 5
        top_influencers = sorted(influencer_ad_request_counts, key=lambda x: x['ad_request_count'], reverse=True)[:5]

        
        stats = {
                'total_users': User.query.count(),
                'flagged_users':User.query.filter(User.flagged==True).count(),
                'total_private_campaigns': Campaign.query.filter(Campaign.visibility==Visibility.PRIVATE).count(),
                'total_public_campaigns': Campaign.query.filter(Campaign.visibility==Visibility.PUBLIC).count(),
                'total_ad_requests': AdRequest.query.count(),
                'active_campaigns_count': Campaign.query.filter(Campaign.status == CampaignStatus.ONGOING).count(),
                'completed_campaigns_count': Campaign.query.filter(Campaign.status == CampaignStatus.COMPLETED).count(),
                'pending_ad_requests_count': AdRequest.query.filter(AdRequest.status==AdRequestStatus.PENDING).count(),
                'accepted_ad_requests_count': AdRequest.query.filter(AdRequest.status==AdRequestStatus.ACCEPTED).count(),
                'rejected_ad_requests_count': AdRequest.query.filter(AdRequest.status==AdRequestStatus.REJECTED).count(),
                'negotiating_ad_requests_count': AdRequest.query.filter(AdRequest.status==AdRequestStatus.NEGOTIATING).count(),
                'completed_ad_requests_count': AdRequest.query.filter(AdRequest.status==AdRequestStatus.COMPLETED).count(),
                'average_campaign_budget': db.session.query(db.func.avg(Campaign.budget)).scalar() or 0,
                'total_campaign_budget': db.session.query(db.func.sum(Campaign.budget)).scalar() or 0,
                'average_ad_request_payment': db.session.query(db.func.avg(AdRequest.payment_amount)).scalar() or 0,
                'top_5_sponsors_by_campaigns': top_sponsors,
                'top_5_influencers_by_ad_requests': top_influencers,
                'average_ad_request_payment_by_campaign': db.session.query(Campaign.id, db.func.avg(AdRequest.payment_amount)).join(AdRequest).group_by(Campaign.id).all(),
                'total_payments_processed': db.session.query(db.func.sum(AdRequest.payment_amount)).filter(AdRequest.status == AdRequestStatus.COMPLETED).scalar() or 0,
                'total_payments_inprocess': db.session.query(db.func.sum(AdRequest.payment_amount)).filter(AdRequest.status == AdRequestStatus.ACCEPTED).scalar() or 0,
                'average_campaign_duration': db.session.query(func.avg(func.julianday(Campaign.end_date) - func.julianday(Campaign.start_date))).scalar() or 0,
                }
        return render_template('admin/admin_dashboard.html', stats=stats)
    except Exception as e:
        flash(f'Error: {str(e)}')
    return redirect(url_for('index'))


#====================================================== Admin Management ====================================================== 
@app.route('/admin/users', methods=['GET'])
@login_required
@roles_required('admin')
def admin_users():
    sponsor_query = (db.session.query(Sponsor).outerjoin(User) 
        .group_by(Sponsor.id))
    
    influencer_query = (db.session.query(Influencer)
                        .outerjoin(AdRequest)
                        .group_by(Influencer.id))

    # Filtering logic for sponsors
    sponsor_username = request.args.get('sponsor_username')
    if sponsor_username:
        sponsor_query = sponsor_query.filter(Sponsor.user.username.contains(sponsor_username))
    sponsor_budget = request.args.get('sponsor_budget')
    if sponsor_budget:
        sponsor_query = sponsor_query.filter(Sponsor.budget >= sponsor_budget)
    sponsor_industry = request.args.get('sponsor_industry')
    if sponsor_industry:
        sponsor_query = sponsor_query.filter(Sponsor.industry.contains(sponsor_industry))
    sponsor_campaigns = request.args.get('sponsor_campaigns')
    

    # Filtering logic for influencers
    influencer_category = request.args.get('influencer_category')
    if influencer_category:
        influencer_query = influencer_query.filter(Influencer.category.contains(influencer_category))
    influencer_followers = request.args.get('influencer_followers')
    if influencer_followers:
        influencer_query = influencer_query.filter(Influencer.followers >= influencer_followers)
    influencer_niche = request.args.get('influencer_niche')
    if influencer_niche:
        influencer_query = influencer_query.filter(Influencer.niche.contains(influencer_niche))
    influencer_ad_requests = request.args.get('influencer_ad_requests')

    sponsors = sponsor_query.all()
    
    # Adding campaign counts to sponsors
    for sponsor in sponsors:
        sponsor.campaigns_count = db.session.query(func.count(Campaign.id)).filter(
            Campaign.sponsor_id == sponsor.id
            ).scalar() or 0
            
    influencers = influencer_query.all()
    # Adding ad request counts to influencers
    for influencer in influencers:
        influencer.ad_requests_count = db.session.query(func.count(AdRequest.id)).filter(
            AdRequest.influencer_id == influencer.id,
            AdRequest.status.in_([AdRequestStatus.ACCEPTED, AdRequestStatus.COMPLETED])
            ).scalar() or 0
    if sponsor_campaigns:
        sponsor_campaigns = int(sponsor_campaigns)
        sponsors = [sponsor for sponsor in sponsors if sponsor.campaigns_count >= sponsor_campaigns]
    if influencer_ad_requests:
        influencer_ad_requests = int(influencer_ad_requests)
        influencers = [influencer for influencer in influencers if influencer.ad_requests_count >= influencer_ad_requests]
        
        
    return render_template('admin/admin_users.html',
                           sponsors=sponsors,
                           influencers=influencers)
    
@app.route('/admin/flag_user', methods=['POST'])
@login_required
@roles_required('admin')
def flag_user():
    user_id = request.form.get('user_id')
    if not user_id:
        flash('No user ID provided', 'error')
        return redirect(url_for('admin_users'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))

    user.flagged = not user.flagged
    db.session.commit()
    flash(f'User {"flagged" if user.flagged else "unflagged"} successfully', 'success')
    return redirect(url_for('admin_users'))


#====================================================== Campaign Management ====================================================== 
@app.route('/campaigns', methods=['GET'])
@login_required
@roles_required('sponsor')
def campaigns():
    complete_old_campaigns()
    try:
        # Retrieve the user and sponsor details
        user_id = session.get('user_id')
        if not user_id:
            flash("User not logged in.")
            return redirect(url_for('index'))

        sponsor = Sponsor.query.filter_by(user_id=user_id).first()
        if not sponsor:
            flash("User is not associated with a sponsor.")
            return redirect(url_for('index'))

       
        campaigns_response = requests.get(f'http://127.0.0.1:5000/api/campaigns', json={'sponsor_id':sponsor.id})

        # Check the response status and handle accordingly
        if campaigns_response.status_code == 200:
            campaigns = campaigns_response.json()
            return render_template('sponsor/campaigns.html', title='Campaigns', campaigns=campaigns)
        else:
            flash(f"Error fetching campaigns: {campaigns_response.status_code}")
            return render_template('sponsor/campaigns.html', title='Campaigns')

    except Exception as e:
        flash(f"Error: {str(e)}")
        return render_template('sponsor/campaigns.html', title='Campaigns')
    
@app.route('/getCampaign/<int:campaign_id>', methods=['GET'])
@login_required
@roles_required('sponsor')
def getCampaign(campaign_id):
    try:
        campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()
        return render_template('sponsor/campaign_details.html', campaign=campaign)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('campaigns'))

@app.route('/create_campaign', methods=['POST'])
@login_required
@roles_required('sponsor')
def create_campaign():
    try:
        user = User.query.get_or_404(session.get('user_id'))
       
        sponsor = Sponsor.query.filter_by(user_id=user.id).first()
        if sponsor:
            pass
        else:
            flash("Sponsor not found", 'danger')
            return redirect(url_for('campaigns'))

        name = request.form['name'].lower()
        description = request.form['description'].lower()
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        budget = request.form['budget']
        niche = request.form['niche']
        
        visibility = request.form['visibility']
        goals = request.form['goals'].lower()

        url = 'http://127.0.0.1:5000/api/campaigns'
        
        data = {
            'name': name,
            'description': description,
            'start_date': start_date,
            'end_date': end_date,
            'budget': float(budget),
            'visibility': visibility,
            'goals': goals,
            'sponsor_id': sponsor.id,   
            'niche': niche
        }

        # Make a POST request to the CampaignAPI
        response = requests.post(url, json=data)
        print(f"Response status code: {response.status_code}")
        

        if response.status_code == 201:
            flash('Campaign created successfully!', 'success')
        else:
            try:
                error_message = response.json().get("message", "Unknown error")
                flash(f'Error: {error_message}', 'danger')
            except ValueError:
                flash(f'Error: {response.content.decode()}', 'danger')
    except Exception as e:
        flash(f'Error in main route: {str(e)}', 'danger')

    return redirect(url_for('campaigns'))

@app.route('/delete_campaign/<int:campaign_id>', methods=['POST'])
@login_required
@roles_required('sponsor')
def delete_campaign(campaign_id):
    url = 'http://127.0.0.1:5000/api/campaigns'
    res = requests.delete(f"{url}/{campaign_id}")
    if res.status_code == 200:
            flash('Campaign deleted successfully!', 'success')
    else:
        error_message = res.json().get("message", "Unknown error")
        flash(f'Error: {error_message}', 'danger')
    return redirect(url_for('campaigns'))

@app.route('/editCampaign/<int:campaign_id>', methods=['GET','POST'])
@login_required
@roles_required('sponsor')
def editCampaign(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id).first_or_404()
    if request.method=='GET':
        return render_template('sponsor/edit_campaign.html', campaign=campaign)
    if request.method=='POST':
        try:
            campaign.name = request.form['name'].lower()
            campaign.description = request.form['description'].lower()
            campaign.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
            campaign.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
            campaign.budget = float(request.form['budget'])
            campaign.visibility = Visibility[request.form['visibility'].upper()]
            campaign.goals = request.form['goals'].lower()
            
            db.session.commit()
            flash('Campaign updated successfully!', 'success')
            return redirect(url_for('campaigns'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('campaigns'))
    

#====================================================== Ad Requests Management ====================================================== 
@app.route('/ad_requests')
@login_required
@roles_required('influencer')
def ad_requests():
    complete_old_campaigns()
    try:
        user_id = session.get('user_id')
        if not user_id:
            flash("User not logged in.")
            return redirect(url_for('index'))
        
        influencer = Influencer.query.filter_by(user_id=user_id).first()
        calculate_reach(influencer.id)
        if not influencer:
            flash("Influencer not found.")
            return redirect(url_for('index'))
        
        # Get sorting and filtering parameters from the query string
        sort_by = request.args.get('sort_by', 'default')
        filter_by = request.args.get('filter_by', '')

        # Start with the base query
        ad_requests_query = AdRequest.query.filter_by(influencer_id=influencer.id)

        # Apply filtering
        if filter_by:
            ad_requests_query = ad_requests_query.join(AdRequest.campaign).filter(Campaign.name.ilike(f'%{filter_by}%'))

        # Apply sorting
        if sort_by == 'payment_amount':
            ad_requests_query = ad_requests_query.order_by(desc(AdRequest.payment_amount))
        elif sort_by == 'campaign_end_date':
            ad_requests_query = ad_requests_query.join(AdRequest.campaign).order_by(Campaign.end_date)

        # Fetch all filtered and sorted ad requests
        ad_requests = ad_requests_query.all()

        AdRequestAlias = aliased(AdRequest)

        campaigns = (Campaign.query
             .filter(
                 Campaign.visibility == Visibility.PUBLIC,
                 Campaign.status != CampaignStatus.COMPLETED,
                 ~exists().where(
                     and_(
                         AdRequestAlias.campaign_id == Campaign.id,
                         AdRequestAlias.influencer_id == influencer.id,
                         AdRequestAlias.status.in_([
                             AdRequestStatus.PENDING,
                             AdRequestStatus.ACCEPTED,
                             AdRequestStatus.NEGOTIATING
                         ])
                     )
                 )
             )
             .all())
        
    except Exception as e:
        print(f"An error occurred: {e}")  # Print the error to the console for debugging
        flash("An error occurred while retrieving ad requests.")
        return redirect(url_for('index'))
    
    return render_template('influencer/ad_requests.html', influencer=influencer, ad_requests=ad_requests, campaigns=campaigns)

@app.route('/acceptAdRequest/<int:adRequestId>', methods=['POST'])
@login_required
@roles_required('sponsor','influencer')
def acceptAdRequest(adRequestId):
    try:
        adRequest = AdRequest.query.filter_by(id=adRequestId).first_or_404()
        adRequest.status = AdRequestStatus.ACCEPTED
        db.session.commit()
        flash('Ad Request Accepted!')
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}")
    return redirect(request.referrer or url_for('index'))


@app.route('/completeAdRequest/<int:adRequestId>', methods=['POST'])
@login_required
@roles_required('sponsor','influencer')
def completeAdRequest(adRequestId):
    try:
        adRequest = AdRequest.query.filter_by(id=adRequestId).first_or_404()
        adRequest.status = AdRequestStatus.COMPLETED
        db.session.commit()
        flash('Ad Request Completed!')
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}")
    return redirect(request.referrer or url_for('index'))


@app.route('/rejectAdRequest/<int:adRequestId>', methods=['POST'])
@login_required
@roles_required('sponsor','influencer')
def rejectAdRequest(adRequestId):
    try:
        adRequest = AdRequest.query.filter_by(id=adRequestId).first_or_404()
        adRequest.status = AdRequestStatus.REJECTED
        db.session.commit()
        flash('Ad Request Rejected.')
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}")
    return redirect(request.referrer or url_for('index'))

@app.route('/update_payment_terms', methods=['POST'])
@login_required
@roles_required('influencer')
def update_payment_terms():
    try:
        ad_request_id = request.form['ad_request_id']
        new_payment_amount = request.form['new_payment_amount']
        
        ad_request = AdRequest.query.get(ad_request_id)
        if ad_request:
            ad_request.payment_amount = new_payment_amount
            ad_request.status = AdRequestStatus.NEGOTIATING
            db.session.commit()
            flash('Payment terms updated and status changed to Negotiating.')
        else:
            flash('Ad request not found.')
    except Exception as e:
        flash('An error occurred while updating payment terms.')

    return redirect(request.referrer or url_for('index'))


#====================================================== Custom error handler for 404 ====================================================== 
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404/404.html'), 404