from flask import Flask, jsonify, request, session, Blueprint
import requests
from flask_mail import Mail, Message
from random import *
from passlib.hash import pbkdf2_sha256
from flask_pymongo import PyMongo
import uuid
from .appconfig import ApplicationConfig
from flask_cors import CORS
from .otp import generate_otp
from .sms import send_sms_otp
import os
# from functools import wraps
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import datetime
from flask_socketio import SocketIO, emit
import redis





app = Flask(__name__)
app.config.from_object(ApplicationConfig)
mail = Mail(app)
CORS(app, supports_credentials=True, origins=["https://e-verification-bkfr.vercel.app", "http://127.0.0.1:5000", "http://127.0.0.1:5173", "https://www.bioentrust.net"])

socketio = SocketIO(app)
JWTManager(app)

# redis_url = ApplicationConfig.REDIS_URL

# Access the Redis URL from appconfig.py
redis_client = redis.StrictRedis(host=os.environ['REDIS_HOSTNAME'], port=6380, password=os.environ['REDIS_ACCESS_KEY'], ssl=True)


# Database
# uri = f"mongodb+srv://TegaDev:{os.environ['MONGODB_PASSWORD']}@cluster1.ze89abk.mongodb.net/?retryWrites=true&w=majority"

mongo1 = PyMongo(app, uri=app.config['MONGO_URI_FIRST'])
db = mongo1.db


# Microservices URLs
microservices = {
    'kyc': 'https://backend-flame-nu.vercel.app/api/v1/'
}


# sms_otp = 0

auth = Blueprint('auth', __name__)

@app.route("/")
def home():
    return ("Server is running fine!")

@auth.route("/protected", methods=["GET"])
@jwt_required()
def home():
    current_user = get_jwt_identity()
    return f"Welcome! {current_user}"


# Send OTP
def send_otp(otp, user_email):
        msg = Message(subject="OTP", sender="mlsayabatech@gmail.com", recipients=[user_email])
        msg.body = str(otp)
        mail.send(msg)
        return jsonify({"message": "OTP sent!"}), otp
     

@auth.route("/signup", methods=["POST"])
def signup():

    user = {
        "_id": uuid.uuid4().hex,
        "first_name": request.json["first_name"],
        "last_name": request.json["last_name"],
        "email": request.json["email"],
        "password": request.json["password"],
        "wallet": 0
    }

    # Check for existing email address and password length
    if db.users.find_one({"email": user["email"]}):
        return jsonify({"error": "Email address already in use"}), 409
    elif len(user['password']) < 8:
        return jsonify({"error": "Password should be more than 7 characters"}), 400

    # Encrypt the password
    user['password'] = pbkdf2_sha256.hash(user["password"])

    # Generate a unique identifier for the OTP request
    otp_request_id = uuid.uuid4().hex

    # Generate a random OTP
    email_otp = generate_otp()

    # Store the user dictionary with the otp_request_id in Redis
    redis_client.hmset(f"user:{otp_request_id}", user)

    # Store the OTP request in Redis with an expiration time of 5 minutes
    redis_client.set(f"{otp_request_id}", int(email_otp), ex=300)  # 300 seconds = 5 minutes

    send_otp(email_otp, user["email"])

    # Return the OTP request ID
    return jsonify({
        "otp_request_id": otp_request_id,
        "response": "otp sent"
        })


@auth.route("/validate-email-otp", methods=["POST"])
def validate_email_otp():
    user_otp = request.json["otp"]
    otp_request_id = request.json["otp_request_id"]

    # Retrieve the stored OTP from Redis
    email_otp = redis_client.get(f"{otp_request_id}")

    if int(email_otp) == int(user_otp):
        user = redis_client.hgetall(f"user:{otp_request_id}")
        user = {k.decode("utf-8"): v.decode("utf-8") for k,v in user.items()}
        user["wallet"] = 0

        # Delete the OTP request from Redis
        redis_client.delete(f"{otp_request_id}")

        # Delete the user from Redis
        redis_client.delete(f"user:{otp_request_id}")

        # Initialize service_charge collection
        service_charge = {
        "_id": user["_id"],
        "email": user["email"],
        "service":{}
        }

        # Initialize client_app collection
        client_app = {
        "_id": user["_id"],
        "apps": []
        }

        # Insert user into the database and start the session
        if db.users.insert_one(user):
            db.client_app.insert_one(client_app)
            db.service_charge.insert_one(service_charge)
            access_token = create_access_token(identity=user["_id"])
            refresh_token = create_refresh_token(identity=user["_id"])
        return jsonify(
            {
                "message": "Logged In",
                "token": {
                    "access": access_token,
                    "refresh": refresh_token
                }
            }
        ), 200
    else:
        return jsonify({"error": "Signup Failed"}), 401
    

@auth.route("/validate-sms-otp", methods=["POST"])
def validate_sms_otp():
    user_otp = request.json["otp"]
    otp_request_id = request.json["otp_request_id"]

    # Retrieve the stored OTP from Redis
    sms_otp = redis_client.get(f"{otp_request_id}")

    if sms_otp == int(user_otp):
        # Delete the OTP request from Redis
        redis_client.delete(f"{otp_request_id}")
        return jsonify({"success": "you've been verified!"}), 200
    else:
        return jsonify({"error": "Invalid OTP key"}), 400
    

@auth.route("/forgot-password", methods=["POST"])
def forgot_password():
    user = db.users.find_one({
            "email": request.json["email"]
        })
    
    if not user:
        return jsonify({"error": "No matching credentials, please sign up!"}), 401
    
    # Send OTP
    
    old_password = {"password": user["password"]}
    new_password = { "$set": { "password": request.json["password"] } }

    db.users.update_one(old_password, new_password)
    



@auth.route("/login", methods=["POST"])
def login():
    user = db.users.find_one({
            "email": request.json["email"]
        })

    if not user:
        return jsonify({"error": "User not found"}), 401


    if user and pbkdf2_sha256.verify(request.json["password"], user["password"]):
        access_token = create_access_token(identity=user["_id"])
        refresh_token = create_refresh_token(identity=user["_id"])
        return jsonify(
            {
                "message": "Logged In",
                "token": {
                    "access": access_token,
                    "refresh": refresh_token
                    }
            }
        ), 200
        
    return jsonify({"error": "Invalid login credentials"}), 401


@app.route("/fund", methods=["POST"])
@jwt_required()
def fund_wallet():
    user_id = get_jwt_identity()
    user = db.users.find_one({"_id": user_id})
    old_wallet_balance = {"wallet": user["wallet"]}
    new_wallet_balance = old_wallet_balance["wallet"] + request.json["amount"]

    new_wallet_balance = { "$set": { "wallet": new_wallet_balance} }
    db.users.update_one({"_id": user_id}, new_wallet_balance)
    user = db.users.find_one({"_id": user_id})
    return user


@app.route("/payment/<service>")
@jwt_required()
def payment(service):
    user_id = get_jwt_identity()
    user = db.users.find_one({"_id": user_id})
    old_wallet_balance = {"wallet": user["wallet"]}

    service_collection = db.service_charge.find_one({"_id": user_id})
    service_charge = {"service": service_collection["service"]}

    charge_amount = service_charge["service"][str(service)]

    if old_wallet_balance["wallet"] >= charge_amount:
        new_wallet_balance = old_wallet_balance["wallet"] - charge_amount
        new_wallet_balance = { "$set": { "wallet": new_wallet_balance} }
        db.users.update_one({"_id": user_id}, new_wallet_balance)
        user = db.users.find_one({"_id": user_id})
    else:
        return jsonify({"error": "insufficient balance"}), 400

    return jsonify({
        "user_id": user["_id"],
        "balance": user["wallet"],
        "email": user["email"],
        "success": "Account debited successfully"
    })


# refresh access token
@auth.route("/refresh")
@jwt_required(refresh=True)
def refresh_access():
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)

    return jsonify({"access": new_access_token})


@app.route('/api/v1/<endpoint>', methods=['POST'])
# @jwt_required()
def kyc_microservice(endpoint):
    # user_id = get_jwt_identity()

    global sms_otp
    sms_otp = generate_otp()
    app_id = request.json["app_id"]
    document = db.client_app.find_one({"apps.app_id": app_id})
    user_id = document["_id"]
    user = db.users.find_one({"_id": user_id})

    old_wallet_balance = {"wallet": user["wallet"]}

    service_collection = db.service_charge.find_one({"_id": user_id})
    service_charge = {"service": service_collection["service"]}

    # Charge amount for accessing the microservice endpoint
    try:
        charge_amount = service_charge["service"]["kyc"]     # Adjust the charge amount as needed
    except KeyError:
        return jsonify({"error": "You do not have access to this service"}), 401


    if old_wallet_balance["wallet"] >= charge_amount:
        # Forward the request to the appropriate microservice endpoint
        microservice_url = f"{microservices['kyc']}/{endpoint}"
        data = request.get_json()
        response = requests.post(microservice_url, json=data)

        # Check if the microservice request was successful
        if response.status_code == 200:
            if endpoint != "facial_comparison":
                microservice_details1 = response.json()
                # new_validatee = microservice_details1["_id"]

                # Charge the client
                new_wallet_balance = old_wallet_balance["wallet"] - charge_amount

                new_wallet_balance = { "$set": { "wallet": new_wallet_balance}}
                db.users.update_one({"_id": user_id}, new_wallet_balance)
                new_request = {"user_id": microservice_details1["data"]["_id"], 
                               "requestTime": microservice_details1["data"]["requesTime"],
                               "charges": charge_amount
                               }
                db.client_app.update_one(
                    { "_id": user_id },
                    { "$push": { "client_users": new_request}}
                        )


                new_wallet_balance = user["wallet"]

                phone_number = microservice_details1["data"]["mobile"]

                # Generate a unique identifier for the OTP request
                otp_request_id = uuid.uuid4().hex

                # Generate a random OTP
                sms_otp = generate_otp()

                # Store the OTP request in Redis with an expiration time of 5 minutes
                redis_client.set(f"{otp_request_id}", int(sms_otp), ex=300)  # 300 seconds = 5 minutes

                res, code = send_sms_otp(sms_otp, phone_number)

                if code != 200:
                    return jsonify({"error": "Something went wrong with kudi"}), 500
                else:
                    return jsonify({"success": "OTP sent!",
                                    "status": "Success",
                                    "otp_request_id": otp_request_id,
                                    # "image1": microservice_details1["data"]["image"],
                                    # "firtName": microservice_details1["data"]["firstName"],
                                    # "lastName": microservice_details1["data"]["lastName"],
                                    # "dateOfBirth": microservice_details1["data"]["dateOfBirth"],
                                    "det": microservice_details1["data"]
                                    }), 200

            else:
                microservice_details2 = response.json()

                # Charge the client
                new_wallet_balance = old_wallet_balance["wallet"] - charge_amount

                new_wallet_balance = { "$set": { "wallet": new_wallet_balance} }
                db.users.update_one({"_id": user_id}, new_wallet_balance)
                user = db.users.find_one({"_id": user_id})
                new_wallet_balance = user["wallet"]

                if microservice_details2["data"]["imageComparison"]["match"]:
                    return jsonify({
                        'success': True,
                        'microservice_details': microservice_details2,
                        "balance": new_wallet_balance
                    }), 200
                else:
                    return jsonify({"error": "Image doesn't match",
                                    "confidence_level": microservice_details2["data"]["imageComparison"]["confidenceLevel"],
                                    "balance": new_wallet_balance}), 400
        else:
            return jsonify({'message': f'Microservice request failed with status code: {response.status_code}'}), 400 
    else:
        return jsonify({'message': 'Insufficient funds'}), 403
    
@app.route('/admin')
@jwt_required()
def admin_websocket():
    client_id = get_jwt_identity()
    
    try:
        data = {}
        # Query MongoDB to get data based on the provided parameter
        client_profile = db.users.find_one({"_id":client_id})
        client_data = db.client_app.find_one({"_id": client_id})
        charges_data = db.service_charge.find_one({"_id": client_id})
        data[client_id] = { "profile": client_profile,  "details": client_data, "Charges": charges_data}
        
        
        return jsonify(data)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin00')
# @jwt_required
def admin00_websocket():
    # admin_id = get_jwt_identity()
    # if admin_id != "An arrray of the admin ids":
        # return ("Not an Admin") 
    try:
        # client_app
# Main Admin's endpoint 
        data = {}
        # Query MongoDB to get data based on the provided parameter
        all_id = (db.client_app.find())
        result = (list(all_id))
        for i in result:
            profile = db.users.find_one({"_id":i["_id"]})
            details = db.client_app.find_one({"_id":i["_id"]})
            charges = db.service_charge.find_one({"_id":i["_id"]})
            data[i["_id"]] = { "profile": profile,  "details": details, "Charges": charges}

        return jsonify(data)


    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500




@app.route("/admin/set-service-price", methods=["POST"])
# @jwt_required()
def set_service_price():
    user_id = request.json["_id"]
    print(user_id)
    # if user_id != "An arrray of the admin ids":
    #     return ("Not an Admin") 
    service_charge = db.service_charge.find_one({"_id": user_id})
    services = request.json["services"]

    new_user_service_charge = {"$set": {"service." + k: v for k, v in services.items()}}
    db.service_charge.update_one({"_id": user_id}, new_user_service_charge)
    service_charge = db.service_charge.find_one({"_id": user_id})

    return service_charge 


@app.route("/create-app", methods=["POST"])
@jwt_required()
def create_app():
    client_id = get_jwt_identity()
    client_apps_details = db.client_app.find_one({"_id": client_id})

    if not client_apps_details:
        return jsonify({"error": "Client not found"}), 404

    # Get JSON object from the frontend
    app_data = request.get_json()

    # Extract relevant information from the JSON object
    app_name = app_data.get("name").lower()
    app_color = app_data.get("color")
    date_time = datetime.datetime.now()
    app_creation_date = date_time.strftime("%B %d, %Y %X")
    app_verification = app_data.get("verification", False)  # Default to False if not provided
    app_user_information = app_data.get("user_information", False)  # Default to False if not provided

    # Check if app_name already exists in the "app" dictionary
    if app_name in client_apps_details["apps"]:
        return jsonify({"error": "App already exists!"}), 409


    # The data to be inserted into the "app" dictionary
    app_entry = {
        "app_id": uuid.uuid4().hex,
        "name": app_name,
        "color": app_color,
        "date_of_creation": app_creation_date,
        "verification": app_verification,
        "user_information": app_user_information,
        "client_users": []
    }

    
    new_client_app = {"$push": {"apps": app_entry}}

    update_app = db.client_app.update_one({"_id": client_id}, new_client_app)
    client_apps_details = db.client_app.find_one({"_id": client_id})

    if update_app.acknowledged:
        return jsonify({"success": "App created successfully",
                        "app_data": client_apps_details["apps"][-1],
                        "client_id": client_id
                        }), 200
    else:
        return jsonify({"error": "App creation failed"}), 401


@app.route("/get-app", methods=["POST"])
def get_app():
    desired_app_id = request.json["app_id"]
    result = db.client_app.find_one({"apps": {"$elemMatch": {"app_id": desired_app_id}}},
        {"_id": 0, "apps.$": 1})
    if not result:
        return jsonify({"error": "App not found"}), 403
    
    return jsonify(result["apps"][0])


app.register_blueprint(auth, url_prefix='/auth')

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)