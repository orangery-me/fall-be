import firebase_admin
from firebase_admin import credentials, initialize_app, db
import config as config
import json
import tempfile

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    json_str = config.Config.GOOGLE_APPLICATION_CREDENTIALS_JSON
    if json_str:
        try:
            credentials_dict = json.loads(json_str)
            print("Initializing Firebase Admin SDK with provided credentials...")
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".json") as tmp:
                json.dump(credentials_dict, tmp)
                tmp_path = tmp.name
                
            cred = credentials.Certificate(tmp_path)
            initialize_app(cred, {'databaseURL': config.Config.FIREBASE_DATABASE_URL})
            
        except Exception as e:
            print(f"Error initializing Firebase Admin SDK: {e}")
    else:
        print("GOOGLE_APPLICATION_CREDENTIALS_JSON is not set in the environment variables.")
        

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import service.process as process
from flasgger import Swagger
import numpy as np
import service.fcm_notify as notify
from tensorflow.keras.models import load_model
import threading

# Initialize Flask app and CORS
app = Flask(__name__)
CORS(app)
swagger = Swagger(app, template_file='swagger_template.yml')

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
        
        for i in range(X.shape[0]):
            sequence = X[i].reshape(1, X.shape[1], X.shape[2])
            # predict activity using the loaded model
            prediction = model.predict(sequence)
            activity = int(np.argmax(prediction[0]) + 1)

            result = send_result_to_firebase(activity, start_time, end_time)
        
            return jsonify({"message": "Predicted", "result": result})
        
    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500
    
def run_location_listener():
    location_ref = db.reference("location")
    location_ref.listen(on_location_change)
    
    
def convert_np_datetime64_to_str(np_datetime):
    py_datetime = np_datetime.astype('M8[ms]').astype(datetime)
    return py_datetime.isoformat()

    
def send_result_to_firebase(activity, start_time, end_time):
    result_ref = db.reference("activity_records")
    status_ref = db.reference("status")
    
    all_records = result_ref.get()
    today = datetime.now().strftime('%d/%m/%Y') 
    print(f"today nek: {today}")
    
    if isinstance(start_time, np.datetime64):
        start_time = convert_np_datetime64_to_str(start_time)
    if isinstance(end_time, np.datetime64):
        end_time = convert_np_datetime64_to_str(end_time)
        
    result_data = {
        "activityType": activity,
        "start_time": start_time,
        "end_time": end_time
    }
        
    existing_key = None
    
    # Set status in Firebase
    status = {
        "is_fall": activity == 8,
        "user_id": user_id,
    }
    status_ref.set(status)
    
    if all_records:
        for new_key, value in all_records.items():
            print("Checking key:", new_key)
            if value.get('user_id') == user_id and value.get('date') == today:
                existing_key = new_key
                break
            
    if existing_key:
        records_ref = result_ref.child(f"{existing_key}/records")
        current_records = records_ref.get() 
        current_records.append(result_data)
        records_ref.set(current_records)
    else:
        new_object = {
            "user_id": user_id,
            "date": today,
            "records": [result_data]
        }
        new_key = datetime.now().strftime("%Y%m%d")
        records_ref = result_ref.child(new_key)
        records_ref.set(new_object)
        existing_key = records_ref.key
        
    return result_data
        
def on_location_change(event):
    # get the first key of data
    data = event.data
    key = next(iter(data)) 
    
    if key != "latitude":
        return
    
    print(f"[INFO] New location change detected: data = {data} with key = {key}")

    dt = datetime.now()
    lat = data['latitude']
    lon = data['longitude']
    
    # get device token from Firebase
    result_ref = db.reference(f"user/{user_id}/deviceToken")
    device_token = result_ref.get()

    # Send notification 
    notify.send_notification(
        device_token,
        "Cảnh báo té ngã",
        f"Phát hiện một cú ngã vào {dt}. Nhấn để xem vị trí.",
        data={
            "lat": str(lat),
            "long": str(lon),
        }
    )    

if __name__ == '__main__':
    threading.Thread(target=run_location_listener, daemon=True).start()
    threading.Thread(target=notify.handle_activity_record, args=(user_id,), daemon=True).start()
    app.run(host='0.0.0.0', port=5050, debug=True)