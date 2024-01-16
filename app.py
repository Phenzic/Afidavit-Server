from flask import Flask, request, jsonify
# from docx import Document
import os
from flask_cors import CORS
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pymongo import MongoClient
from bson import ObjectId
import uuid


app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://e-verification-bkfr.vercel.app", "http://127.0.0.1:5000", "http://127.0.0.1:5173", "https://www.bioentrust.net"])


password = os.getenv('mongo_password')
mongo_uri = f'mongodb+srv://new_user:{password}@cluster0.ckb7jdf.mongodb.net/?retryWrites=true&w=majority'
print(password)
print(password)
client = MongoClient(mongo_uri)
db = client.db
court_data = db['court_data']
affidavit_data = db['affidavit_data']

@app.route('/court-signup', methods=['POST'])
def court_signup():
    """
    Endpoint for court signup.
    """

    try:
        data = request.json["data"]
        existing_user = court_data.find_one({'username': data['username']})
        if existing_user:
            raise Exception('User with this username already exists')

        inserted_data = court_data.insert_one(data)

        response_message = {
            'status': 'success',
            'message': 'Data added to MongoDB collection',
            'inserted_id': str(inserted_data.inserted_id)
        }

        return jsonify(response_message), 200

    except Exception as e:
        error_message = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(error_message), 500

@app.route('/')
def index():
    """
    Default endpoint.
    """
    return 'Welcome to the e-affidavit server!'

@app.route('/get_id', methods=['POST'])
def get_id():
    # Endpoint to get app ID.
    # TODO: Implement the logic to get the app ID
    try:
        app_id = request.json["app_id"]
        print(app_id)
        obj = court_data.find_one({'_id': ObjectId(app_id)})
        existing_user = court_data.find_one({'_id': ObjectId(app_id)})
        if existing_user:
            response_message = {
                'status': 'success',
                'message': 'App ID found',
                'data': {
                    '_id': str(existing_user['_id']),  # Convert ObjectId to string
                    'username': existing_user['username'],
                    'color': existing_user['color'],
                    'verification': existing_user['verification'],
                    'user_information': existing_user['user_information'],
                    'on_verification': existing_user['on_verification'],
                    'redirect_url': existing_user['redirect_url'],
                    'courtLogo': existing_user['courtLogo'],
                    'courtName': existing_user['courtName'],
                    'courtAddress': existing_user['courtAddress'],
                    'commissionerForOathSignature': existing_user['commissionerForOathSignature']
                }
            }
            return jsonify(response_message), 200
        else:
            raise Exception('User with this app ID already exists')
    except Exception as e:
        error_message = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(error_message), 500



@app.route('/keep_affidavit', methods=['POST'])
def keep_affidavit():
    try:
        data = request.json["data"]
        # data['id'] = str(uuid.uuid4())
        # print(data["id"])
        print()
        existing_data = affidavit_data.find_one({'id': data['id']})
        if existing_data:
            # return(existing_data, "Affidavit already exists")
            raise Exception('Affidavit already exists',
                            existing_data['id'])

        inserted_data = affidavit_data.insert_one(data)

        response_message = {
            'status': 'success',
            'message': 'Data added to MongoDB collection',
            'inserted_id': str(inserted_data.inserted_id)
        }

        return jsonify(response_message), 200

    except Exception as e:
        error_message = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(error_message), 500
