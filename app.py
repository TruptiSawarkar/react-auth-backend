import os
import firebase_admin
from firebase_admin import credentials, auth, firestore
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure CORS
CORS(app, supports_credentials=True, origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173"
])

# Initialize Firebase Admin SDK
firebase_initialized = False
db = None

try:
    # Check if service account key exists
    if not os.path.exists("firebase-admin-key.json"):
        raise FileNotFoundError("firebase-admin-key.json not found!")
    
    cred = credentials.Certificate("firebase-admin-key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    firebase_initialized = True
    print("✅ Firebase Admin SDK initialized successfully!")
    print("✅ Firestore client connected!")
except Exception as e:
    print(f"❌ Firebase initialization error: {e}")
    print("⚠️  The app will run but Firebase features won't work")

# ========== AUTHENTICATION DECORATOR ==========

def verify_token(f):
    """Decorator to verify Firebase ID token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not firebase_initialized:
            return jsonify({'error': 'Firebase not configured'}), 500
        
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401
        
        token = auth_header.split('Bearer ')[1]
        
        try:
            decoded_token = auth.verify_id_token(token)
            request.user_id = decoded_token['uid']
            request.user_email = decoded_token.get('email')
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': f'Invalid token: {str(e)}'}), 401
    
    return decorated_function

# ========== API ENDPOINTS ==========

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'firebase_initialized': firebase_initialized,
        'message': 'Backend is running!'
    })

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """Simple test endpoint without authentication"""
    return jsonify({
        'success': True,
        'message': 'Backend connection successful!',
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/api/user/profile', methods=['GET'])
@verify_token
def get_user_profile():
    """Get user profile from Firestore"""
    try:
        user_ref = db.collection('users').document(request.user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            return jsonify({
                'success': True,
                'profile': user_doc.to_dict()
            })
        else:
            # Create default profile
            default_profile = {
                'email': request.user_email,
                'display_name': '',
                'bio': '',
                'created_at': datetime.datetime.now().isoformat(),
                'settings': {
                    'notifications': True,
                    'theme': 'light'
                }
            }
            user_ref.set(default_profile)
            return jsonify({
                'success': True,
                'profile': default_profile
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/profile', methods=['PUT'])
@verify_token
def update_user_profile():
    """Update user profile"""
    try:
        data = request.json
        user_ref = db.collection('users').document(request.user_id)
        
        update_data = {}
        if 'display_name' in data:
            update_data['display_name'] = data['display_name']
        if 'bio' in data:
            update_data['bio'] = data['bio']
        
        update_data['updated_at'] = datetime.datetime.now().isoformat()
        
        if update_data:
            user_ref.update(update_data)
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/data', methods=['POST'])
@verify_token
def save_user_data():
    """Save custom user data"""
    try:
        data = request.json
        user_ref = db.collection('user_data').document(request.user_id)
        
        user_ref.set({
            'data': data,
            'updated_at': datetime.datetime.now().isoformat()
        }, merge=True)
        
        return jsonify({
            'success': True,
            'message': 'Data saved successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/data', methods=['GET'])
@verify_token
def get_user_data():
    """Get custom user data"""
    try:
        user_ref = db.collection('user_data').document(request.user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return jsonify({
                'success': True,
                'data': user_data.get('data', {})
            })
        else:
            return jsonify({
                'success': True,
                'data': {}
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users', methods=['GET'])
@verify_token
def get_all_users():
    """Get all users (admin only)"""
    try:
        # Check admin claim
        user = auth.get_user(request.user_id)
        if not user.custom_claims or not user.custom_claims.get('admin'):
            return jsonify({'error': 'Admin access required'}), 403
        
        # List users
        users_list = []
        for user in auth.list_users().iterate_all():
            users_list.append({
                'uid': user.uid,
                'email': user.email,
                'disabled': user.disabled,
                'created_at': user.user_metadata.creation_timestamp
            })
        
        return jsonify({
            'success': True,
            'users': users_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ========== RUN SERVER ==========

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 FLASK BACKEND SERVER")
    print("="*50)
    print(f"📍 Status: {'✅ Firebase Ready' if firebase_initialized else '⚠️  Firebase Not Configured'}")
    print(f"🌐 Port: 5000")
    print(f"📡 API URL: http://localhost:5000/api")
    print("\n📋 Available Endpoints:")
    print("   GET  /api/health")
    print("   GET  /api/test")
    print("   GET  /api/user/profile")
    print("   PUT  /api/user/profile")
    print("   GET  /api/user/data")
    print("   POST /api/user/data")
    print("   GET  /api/admin/users")
    print("\n" + "="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)