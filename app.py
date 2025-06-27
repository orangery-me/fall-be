from tensorflow.keras.models import load_model
from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS
from datetime import datetime
import service.fcm_notify as notify
import service.process as process
import firebase_admin
from flasgger import Swagger
from firebase_admin import credentials, initialize_app
import config as config
import numpy as np

# Initialize Flask app and CORS
app = Flask(__name__)
CORS(app)
swagger = Swagger(app, template_file='swagger_template.yml')

# Initialize MongoDB client and database
client = MongoClient(config.Config.MONGO_URI)
db = client["healthy_app"]
records_collection = db["activity_records"]
user = db["user"]

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate("healthy_apps.json")
    firebase_admin.initialize_app(cred)

# Load model
model = load_model("model/LSTM_model.h5")
user_id = "user_1029357990"

@app.route('/')
def home():
    return "Welcome to the API!"

@app.route('/predict', methods=['POST'])
def predict_activity():
    raw_data = request.json.get("data")
    if not raw_data:
        return jsonify({"error": "Missing data"}), 400

    try:
        X, start_time, end_time = process.process_data(raw_data)

        results = []
        for i in range(X.shape[0]):
            sequence = X[i].reshape(1, X.shape[1], X.shape[2])
            # predict activity using the loaded model
            prediction = model.predict(sequence)
            activity = int(np.argmax(prediction[0]) + 1)

            result_data = {
                "activityType": activity,
                "start_time": start_time.isoformat() if isinstance(start_time, datetime) else str(start_time),
                "end_time": end_time.isoformat() if isinstance(end_time, datetime) else str(end_time)
            }
            results.append(result_data)

        # Writing results to MongoDB
        now = datetime.now()
        today = now.strftime('%d/%m/%Y')
        custom_id = now.strftime("%Y%m%d")

        existing_record = records_collection.find_one({
            "user_id": user_id,
            "date": today
        })

        if existing_record:
            records_collection.update_one(
                {"_id": existing_record["_id"]},
                {"$push": {"records": {"$each": results}}}
            )
        else:
            new_record = {
                "_id": custom_id,
                "user_id": user_id,
                "date": today,
                "records": results
            }
            records_collection.insert_one(new_record)

        # update status
        user.update_one(
            {"_id": user_id},
            {"$set": {"is_fall": any(r["activityType"] == 8 for r in results)}},
            upsert=True
        )

        return jsonify({"message": "Predicted", "results": results})

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500

@app.route('/device-token', methods=['POST'])
def register_device_token():
    data = request.json
    token = data.get("token")
    
    if not token:
        return jsonify({"error": "Missing device token"}), 400

    user.update_one(
        {"_id": user_id},
        {"$set": {"token": token}},
        upsert=True
    )
    return jsonify({"message": "Device token registered successfully"})

    
@app.route('/location', methods=['POST'])
def location_alert():
    data = request.json
    lat = data.get("latitude")
    lon = data.get("longitude")
    custom_id = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3] 

    if not lat or not lon:
        return jsonify({"error": "Missing latitude or longitude"}), 400

    now = datetime.now().strftime('%H:%M:%S')
    
    # save location to MongoDB
    location_data = {
        "_id": custom_id,
        "latitude": lat,
        "longitude": lon,
        "user_id": user_id,
    }
    db.locations.insert_one(location_data)
    
    # get device token
    user_data = user.find_one({"_id": user_id})
    if not user_data or "token" not in user_data:
        return jsonify({"error": "User device token not found"}), 404
    device_token = user_data["token"]
    
    # send notification
    notify.send_notification(
        device_token,
        "Cảnh báo té ngã",
        f"Phát hiện một cú ngã vào {now}. Nhấn để xem vị trí.",
        data={
            "_id": custom_id,
            "lat": str(lat),
            "long": str(lon),
            "user_id": user_id,
        }
    )

    return jsonify({"message": "Location alert sent"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)