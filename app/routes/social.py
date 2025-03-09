# app/routes/social.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.user import User
from app.models.social import Achievement, ActivityFeed
from sqlalchemy import desc
from datetime import datetime, timedelta

social_bp = Blueprint('social', __name__)

# app/routes/social.py
@social_bp.route('/all-users', methods=['GET'])
@jwt_required()
def get_all_users():
    current_user_id = int(get_jwt_identity())
    users = User.query.all()
    
    # Exclude the current user from the list
    users = [user for user in users if user.id != current_user_id]
    print(users, current_user_id)
    
    return jsonify({
        'users': [{
            'id': user.id,
            'username': user.username,
            'email': user.email
        } for user in users]
    }), 200

# Get Followers
@social_bp.route('/followers', methods=['GET'])
@jwt_required()
def get_followers():
    current_user_id = get_jwt_identity()
    current_user = User.query.get_or_404(current_user_id)
    
    # Fetch followers
    followers = current_user.followers.all()
    
    return jsonify({
        'followers': [{
            'id': follower.id,
            'username': follower.username,
            'email': follower.email,
            'isFollowingYou': follower.is_following(current_user)
        } for follower in followers]
    }), 200

# Get Following
@social_bp.route('/following', methods=['GET'])
@jwt_required()
def get_following():
    current_user_id = get_jwt_identity()
    current_user = User.query.get_or_404(current_user_id)
    
    # Fetch users the current user is following
    following = current_user.following.all()
    
    return jsonify({
        'following': [{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'isFollowingYou': user.is_following(current_user)
        } for user in following]
    }), 200

# Follow a User
@social_bp.route('/follow/<int:user_id>', methods=['POST'])
@jwt_required()
def follow_user(user_id):
    current_user_id = get_jwt_identity()
    
    if current_user_id == user_id:
        return jsonify({'error': 'Cannot follow yourself'}), 400
    
    current_user = User.query.get_or_404(current_user_id)
    user_to_follow = User.query.get_or_404(user_id)
    
    if current_user.is_following(user_to_follow):
        return jsonify({'error': 'Already following this user'}), 400
    
    current_user.follow(user_to_follow)
    db.session.commit()
    
    # Create activity feed entry
    activity = ActivityFeed(
        user_id=current_user_id,
        activity_type='follow',
        content=f"Started following {user_to_follow.username}",
        related_id=user_id
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'message': f'Now following {user_to_follow.username}'}), 200

# Unfollow a User
@social_bp.route('/unfollow/<int:user_id>', methods=['POST'])
@jwt_required()
def unfollow_user(user_id):
    current_user_id = get_jwt_identity()
    
    current_user = User.query.get_or_404(current_user_id)
    user_to_unfollow = User.query.get_or_404(user_id)
    
    if not current_user.is_following(user_to_unfollow):
        return jsonify({'error': 'Not following this user'}), 400
    
    current_user.unfollow(user_to_unfollow)
    db.session.commit()
    
    return jsonify({'message': f'Unfollowed {user_to_unfollow.username}'}), 200

# Activity Feed
@social_bp.route('/feed', methods=['GET'])
@jwt_required()
def get_activity_feed():
    current_user_id = get_jwt_identity()
    user_id = request.args.get('user_id')  # Get user_id from query params

    # Fetch activities for the specified user
    if user_id:
        activities = ActivityFeed.query.filter_by(user_id=user_id).order_by(ActivityFeed.created_at.desc()).limit(50).all()
    else:
        # Default behavior: Fetch activities for the current user
        activities = ActivityFeed.query.filter_by(user_id=current_user_id).order_by(ActivityFeed.created_at.desc()).limit(50).all()

    return jsonify({
        'activities': [activity.to_dict() for activity in activities]
    }), 200

# Achievements
@social_bp.route('/achievements', methods=['GET'])
@jwt_required()
def get_achievements():
    current_user_id = get_jwt_identity()
    
    achievements = Achievement.query.filter_by(user_id=current_user_id)\
        .order_by(Achievement.created_at.desc()).all()
    
    return jsonify({
        'achievements': [achievement.to_dict() for achievement in achievements]
    }), 200

# Leaderboard
@social_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    timeframe = request.args.get('timeframe', 'week')  # week, month, all-time
    
    if timeframe == 'week':
        date_limit = datetime.utcnow() - timedelta(days=7)
    elif timeframe == 'month':
        date_limit = datetime.utcnow() - timedelta(days=30)
    else:
        date_limit = datetime.min
    
    # Get users with their waste reduction stats
    from app.models.waste import WasteLog
    
    leaderboard = db.session.query(
        User,
        db.func.count(WasteLog.id).label('total_logs'),
        db.func.sum(WasteLog.amount).label('total_amount')
    ).join(WasteLog).filter(
        WasteLog.date >= date_limit
    ).group_by(User.id).order_by(
        db.desc('total_logs'),
        db.desc('total_amount')
    ).limit(10).all()
    
    return jsonify({
        'timeframe': timeframe,
        'leaders': [{
            'username': user.username,
            'total_logs': total_logs,
            'total_amount': float(total_amount) if total_amount else 0
        } for user, total_logs, total_amount in leaderboard]
    }), 200