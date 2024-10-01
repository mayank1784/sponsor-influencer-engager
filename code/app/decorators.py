from functools import wraps
from flask import session, redirect, url_for, flash, abort
from app.models import User

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You need to be logged in to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is in session
            if 'user_id' not in session:
                abort(401, description="Authorization required.")
            
            # Get the user's role from the session
            user_role = session.get('role')
            
            # Check if the role is in the allowed roles
            if user_role not in roles:
                abort(403, description="Forbidden: You do not have the required role.")
            
            # Retrieve the user from the database
            user = User.query.get(session['user_id'])
            
            # Check if user is flagged
            if user and user.flagged:
                abort(403, description="Forbidden: Your account is flagged.")
            
            # Call the original function if all checks pass
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator