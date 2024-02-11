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
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from bson.json_util import dumps


app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://e-verification-bkfr.vercel.app", "http://127.0.0.1:5000", "http://127.0.0.1:5173", "https://www.bioentrust.net"])


username = os.getenv('MONGODB_USERNAME')
password = os.getenv('MONGODB_PASSWORD')


mongo_uri = f'mongodb+srv://{username}:{password}@cluster0.ckb7jdf.mongodb.net/?retryWrites=true&w=majority'
client = MongoClient(mongo_uri)
db = client.db
court_data = db['court_data']
affidavit_data = db['affidavit_data']


# @dev signs up a court details and updates it, only if the creator calls the request,
# @dev returns the court_id of the court that was signed up
@app.route('/court-signup', methods=['POST'])
@jwt_required()
def court_signup():
    current_user = get_jwt_identity()
    """
    Endpoint for court signup.
    """
    try:
        data = request.json["data"]
        data["creator"] = current_user
        existing_user = court_data.find_one({'name': data['name']})
        if existing_user:
            court_data.update_one({'name': data['name']}, {'$set': data})
        else:
            court_data.insert_one(data)            
        # inserted_data = court_data.insert_one(data)
        new_data = court_data.find_one({'name': data['name']})


        response_message = {
            'status': 'success',
            'message': 'Data added to MongoDB collection',
            'court_id': str(new_data['_id']),
            }

        return jsonify(response_message), 200

    except Exception as e:
        error_message = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(error_message), 500


something = os.getenv('SOMETHING')
@app.route('/some')
def some():
    return jsonify(os.getenv('SOMETHING'))


@app.route('/')
def index():
    """
    Default endpoint.
    """
    return 'Welcome to the e-affidavit server!'


@app.route('/get_court_details', methods=['POST'])
def get_court_details():
    # Endpoint to get app ID.
    # TODO: Implement the logic to get the app ID
    try:
        app_id = request.json["app_id"]
        existing_user = court_data.find_one({'_id': ObjectId(app_id)})
        if existing_user:    
            existing_user.pop('_id')
            existing_user["_id"] = app_id  # Exclude the '_id' field from the response
            response_message = {
                'status': 'success',
                'message': 'App ID found',
                'data': existing_user
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



@app.route('/save_affidavit', methods=['POST'])
def save_affidavit():
    try:
        data = request.json["data"]
        existing_data = affidavit_data.find_one({'id': data['id']})
        if existing_data:
            # return(existing_data, "Affidavit already exists")
            raise Exception('Affidavit already exists',
                            existing_data['id'])

        inserted_data = affidavit_data.insert_one(data)
        new_data = affidavit_data.find_one({'id': data['id']})

        response_message = {
            'status': 'success',
            'message': 'Data added to MongoDB collection',
            'inserted_id': str(inserted_data.inserted_id),
            'new_data': str(new_data["_id"])
        }

        return jsonify(response_message), 200

    except Exception as e:
        error_message = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(error_message), 500
    


@app.route('/getAllCourtAffidavit', methods=['POST'])
def get_court_affidavit():
    court_id = request.json["court_id"]
    try:
        result = affidavit_data.find({'court_id': court_id})
        documents = [doc for doc in result]
        for doc in documents:
            # doc.pop('_id', None)  # Remove the "_id" variable
            doc['_id'] = str(doc['_id'])  # Convert ObjectId to string
        return dumps(documents), 200
    except Exception as e:
        error_message = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(error_message), 500

@app.route('/getAllCourtAffidavitId', methods=['POST'])
def get_affidavit():
    court_id = request.json["court_id"]
    try:
        results = affidavit_data.find({'court_id': court_id}, {'_id': 1})
        # Convert _id to string
        results = [{'_id': str(res['_id'])} for res in results]
        return jsonify(results), 200
    except Exception as e:
        error_message = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(error_message), 500