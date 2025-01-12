from flask import Flask, session, request, jsonify, render_template, redirect, url_for, flash
from flask_pymongo import PyMongo
from pymongo import MongoClient
from flask_cors import CORS
from bson import ObjectId
import google.generativeai as genai
from datetime import datetime
# from dotenv import load_dotenv
import json
import re
import os

# load_dotenv()

app = Flask(__name__)
CORS(app)
genai.configure(api_key='AIzaSyCRxcQJL0lRiT8nd71y4Kvwm5WTE9rwuZ0')
model = genai.GenerativeModel('gemini-pro')

app.config["MONGO_URI"] = "mongodb+srv://vasudha:vasudha@cluster0.0vkno.mongodb.net/usersDB?authSource=admin&retryWrites=true&w=majority&readPreference=primary"
mongo = PyMongo(app)

try:
    client = MongoClient('mongodb+srv://vasudha:vasudha@cluster0.0vkno.mongodb.net/usersDB?authSource=admin&retryWrites=true&w=majority&readPreference=primary')
    db = client.get_database("usersDB")
    print("Databases:", client.list_database_names())
    print("Connection successful!")
except Exception as e:
    print("Connection failed:", e)

try:
    client = MongoClient('mongodb+srv://vasudha:vasudha@cluster0.0vkno.mongodb.net/usersDB?authSource=admin&retryWrites=true&w=majority&readPreference=primary')
    db = client.get_database("usersDB")
    
    # Create notifications collection if it doesn't exist
    if 'notifications' not in db.list_collection_names():
        db.create_collection('notifications')
        print("Created notifications collection")
        # Create indexes for better query performance
        db.notifications.create_index([("timestamp", -1)])
        db.notifications.create_index([("read", 1)])
    
    print("Databases:", client.list_database_names())
    print("Connection successful!")
except Exception as e:
    print("Connection failed:", e)

@app.route('/')
def home():
    try:
        # Explicitly fetch only scenarios marked as visible to users
        scenarios = list(mongo.db.admin.find({
            "visible_to_users": True
        }).sort('user_approval_date', -1))
        return render_template('index.html', scenarios=scenarios)
    except Exception as e:
        print(f"Error fetching scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500

@app.route('/admindashboard')
def admin_dashboard():
    scenarios = mongo.db.admin.find()
    return render_template('admindashboard.html', scenarios=scenarios)

@app.route('/summary')
def get_analysis_summary():
    try:
        # Get the most recent analysis from the database
        analysis = mongo.db.conversation_analyses.find_one(
            sort=[('timestamp', -1)]
        )
        
        if not analysis:
            return render_template(
                'summary.html', 
                error="No analysis data found"
            )

        return render_template(
            'summary.html', 
            analysis=analysis['analysis']
        )

    except Exception as e:
        print(f"Error retrieving analysis: {str(e)}")
        return render_template(
            'summary.html', 
            error="Error retrieving analysis data"
        )

@app.route('/get_prompt', methods=['POST'])
def get_prompt():
    try:
        request_data = request.json
        print("Received Request Data:", request_data)

        scenario_id = request.json.get('scenario_id', '')
        print(f"Extracted Scenario ID: {scenario_id}")

        if not scenario_id:
            return jsonify({"error": "No scenario ID provided"}), 400
        
        try:
            object_id = ObjectId(scenario_id)
        except Exception as e:
            print(f"Invalid ObjectId: {e}")
            return jsonify({"error": "Invalid scenario ID format"}), 400
        
        scenario_data = mongo.db.admin.find_one({"_id": object_id})

        if scenario_data and "prompt" in scenario_data:
            updated_prompt = scenario_data["prompt"]
            return jsonify({"prompt": updated_prompt})
        else:
            return jsonify({"error": "Scenario not found"}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to fetch prompt"}), 500

@app.route('/index')
def question():
    scenarios = mongo.db.admin.find({"visible_to_users": True})
    return render_template('index.html', scenarios=scenarios)

@app.route('/create', methods=['POST'])
def create_scenario():
    try:
        data = request.json
        result = mongo.db.admin.insert_one({
            "scenario": data['scenario'],
            "prompt": data['prompt'],
            "question": data['question'],
            "visible_to_users": False
        })
        return jsonify({"message": "Roleplay created successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"Error creating scenario: {e}")
        return jsonify({"error": "Failed to create scenario"}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        history = mongo.db.admin.find()
        return jsonify([
            {
                "_id": str(doc['_id']),
                "scenario": doc.get('scenario', ''),
                "prompt": doc.get('prompt', ''),
                "question": doc.get('question', ''),
                "visible_to_users": doc.get('visible_to_users', False),
                "visible_to_admin": doc.get('visible_to_admin', False)
            }
            for doc in history
        ]), 200
    except Exception as e:
        print(f"Error fetching history: {e}")
        return jsonify({"error": "Failed to fetch history"}), 500

@app.route('/delete/<scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    try:
        object_id = ObjectId(scenario_id)
        result = mongo.db.admin.delete_one({'_id': object_id})
        
        if result.deleted_count > 0:
            return jsonify({"message": "Scenario deleted successfully"}), 200
        else:
            return jsonify({"error": "Scenario not found"}), 404
    except Exception as e:
        print(f"Error deleting scenario: {e}")
        return jsonify({"error": "Failed to delete scenario"}), 500

@app.route('/delete-batch', methods=['POST'])
def delete_batch():
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        result = mongo.db.admin.delete_many({'_id': {'$in': object_ids}})
        
        if result.deleted_count > 0:
            return jsonify({
                "message": f"Successfully deleted {result.deleted_count} scenarios",
                "deleted_count": result.deleted_count
            }), 200
        else:
            return jsonify({"error": "No scenarios found to delete"}), 404
    except Exception as e:
        print(f"Error in batch delete: {e}")
        return jsonify({"error": "Failed to delete scenarios"}), 500

@app.route('/toggle_admin_visibility', methods=['POST'])
def toggle_admin_visibility():
    """Super admin endpoint to toggle visibility for admins"""
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        # Update visibility for admins
        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'visible_to_admin': True}}
        )
        
        # # Set others to not visible to admin
        # mongo.db.admin.update_many(
        #     {'_id': {'$nin': object_ids}},
        #     {'$set': {'visible_to_admin': False}}
        # )

        return jsonify({
            "message": f"Successfully updated admin visibility for {result.modified_count} scenarios",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling admin visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500

@app.route('/toggle_visibility', methods=['POST'])
def toggle_visibility():
    """Super admin endpoint to toggle visibility for users"""
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        # Update visibility for users
        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'visible_to_users': True}}
        )

        return jsonify({
            "message": f"Successfully updated visibility for {result.modified_count} scenarios",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500
@app.route('/admin')
def admin_view():
    """Route for the regular admin dashboard"""
    return render_template('admin_dashboard.html')

@app.route('/admin/scenarios')
def get_admin_scenarios():
    """Get scenarios that are visible to admin (approved by super admin)"""
    try:
        # Get all scenarios that super admin has made visible to admin
        scenarios = list(mongo.db.admin.find({"visible_to_admin": True}))
        return jsonify([
            {
                "_id": str(doc['_id']),
                "scenario": doc.get('scenario', ''),
                "prompt": doc.get('prompt', ''),
                "question": doc.get('question', ''),
                "visible_to_users": doc.get('visible_to_users', False)
            }
            for doc in scenarios
        ]), 200
    except Exception as e:
        print(f"Error fetching admin scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500
    

@app.route('/admin/toggle_visibility', methods=['POST']) 
def admin_toggle_visibility():
    try:
        scenario_ids = request.json.get('ids', [])
        action = request.json.get('action', 'add')
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        # Verify these scenarios are visible to admin first
        visible_to_admin = mongo.db.admin.count_documents({
            '_id': {'$in': object_ids},
            'visible_to_admin': True
        })
        
        if visible_to_admin != len(scenario_ids):
            return jsonify({"error": "Unauthorized access to some scenarios"}), 403

        if action == 'add':
            # Get scenario details for notifications
            scenarios = mongo.db.admin.find({'_id': {'$in': object_ids}})
            
            # Create notifications for each scenario but DON'T make visible to users yet
            for scenario in scenarios:
                notification = {
                    'title': 'New Scenario Available',
                    'message': f"New scenario available: '{scenario.get('scenario', 'Unnamed')}'",
                    'timestamp': datetime.now(),
                    'read': False,
                    'accepted': False,
                    'scenario_id': str(scenario['_id']),
                    'source': 'admin'
                }
                mongo.db.notifications.insert_one(notification)
                
                # Update scenario to track notification status
                mongo.db.admin.update_one(
                    {'_id': scenario['_id']},
                    {
                        '$set': {
                            'notification_sent': True,
                            'notification_date': datetime.now()
                        }
                    }
                )

        return jsonify({
            "message": "Notifications sent successfully",
            "modified_count": len(scenario_ids)
        }), 200
    except Exception as e:
        print(f"Error in visibility toggle: {e}")
        return jsonify({"error": str(e)}), 500
           
@app.route('/remove_admin_visibility', methods=['POST'])
def remove_admin_visibility():
    """Remove scenarios from admin view"""
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'visible_to_admin': False}}
        )

        return jsonify({
            "message": f"Successfully removed admin visibility for {result.modified_count} scenarios",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error removing admin visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500

@app.route('/notifications')
def get_notifications():
    try:
        notifications = list(mongo.db.notifications.find().sort('timestamp', -1))
        return jsonify([{
            'id': str(notification['_id']),
            'title': notification.get('title', ''),
            'message': notification.get('message', ''),
            'time': notification.get('timestamp').strftime("%Y-%m-%d %H:%M:%S"),
            'read': notification.get('read', False),
            'accepted': notification.get('accepted', False),
            'scenario_id': notification.get('scenario_id', ''),
            'source': notification.get('source', 'unknown')  # Include source in response
        } for notification in notifications])
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return jsonify([])
    
    
@app.route('/notifications/<notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """Mark a specific notification as read"""
    try:
        result = mongo.db.notifications.update_one(
            {'_id': ObjectId(notification_id)},
            {'$set': {'read': True}}
        )
        return jsonify({'success': True, 'modified_count': result.modified_count})
    except Exception as e:
        print(f"Error marking notification as read: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    """Mark all notifications as read"""
    try:
        result = mongo.db.notifications.update_many(
            {},
            {'$set': {'read': True}}
        )
        return jsonify({'success': True, 'modified_count': result.modified_count})
    except Exception as e:
        print(f"Error marking all notifications as read: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/notifications/unread-count')
def get_unread_count():
    """Get count of unread notifications"""
    try:
        count = mongo.db.notifications.count_documents({'read': False})
        return jsonify({'count': count})
    except Exception as e:
        print(f"Error getting unread count: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/admin/current-user-scenarios')
def get_current_user_scenarios():
    """Get scenarios that are currently visible to users"""
    try:
        scenarios = mongo.db.admin.find({"visible_to_users": True})
        return jsonify([{
            "_id": str(doc['_id']),
            "scenario": doc.get('scenario', ''),
            "prompt": doc.get('prompt', ''),
            "question": doc.get('question', ''),
            "approval_date": doc.get('user_approval_date', None)
        } for doc in scenarios]), 200
    except Exception as e:
        print(f"Error fetching user scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500

@app.route('/superadmin/toggle_admin_visibility', methods=['POST'])
def superadmin_toggle_admin_visibility():
    try:
        scenario_ids = request.json.get('ids', [])
        action = request.json.get('action', 'add')  # 'add' or 'remove'
        
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        if action == 'add':
            # Update visibility and add approval date for admin
            result = mongo.db.admin.update_many(
                {'_id': {'$in': object_ids}},
                {
                    '$set': {
                        'visible_to_admin': True,
                        'admin_approval_date': datetime.now().isoformat()
                    }
                }
            )
        else:  # remove
            # Remove visibility from admin
            result = mongo.db.admin.update_many(
                {'_id': {'$in': object_ids}},
                {
                    '$set': {'visible_to_admin': False},
                    '$unset': {'admin_approval_date': ''}
                }
            )

        return jsonify({
            "message": f"Successfully {'added to' if action == 'add' else 'removed from'} admin view",
            "modified_count": result.modified_count
        }), 200
    except Exception as e:
        print(f"Error toggling admin visibility: {e}")
        return jsonify({"error": "Failed to update scenarios"}), 500
    
@app.route('/admin/delete_scenario/<scenario_id>', methods=['DELETE'])
def admin_delete_scenario(scenario_id):
    """Admin endpoint to delete scenarios from users"""
    try:
        # First verify the scenario exists and is visible to admin
        scenario = mongo.db.admin.find_one({
            '_id': ObjectId(scenario_id),
            'visible_to_admin': True
        })
        
        if not scenario:
            return jsonify({"error": "Scenario not found or not accessible"}), 404

        # Update the scenario to remove visibility
        result = mongo.db.admin.update_one(
            {'_id': ObjectId(scenario_id)},
            {
                '$set': {
                    'visible_to_users': False
                },
                '$unset': {
                    'user_approval_date': '',
                    'sent_by': ''
                }
            }
        )

        # Delete any related notifications
        mongo.db.notifications.delete_many({
            'scenario_id': scenario_id
        })

        return jsonify({
            "success": True,
            "message": "Scenario removed successfully"
        }), 200

    except Exception as e:
        print(f"Error deleting scenario: {str(e)}")
        return jsonify({
            "error": str(e),
            "message": "Failed to delete scenario"
        }), 500    
@app.route('/admin/delete_scenarios', methods=['POST'])
def admin_delete_scenarios():
    try:
        scenario_ids = request.json.get('ids', [])
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        # Verify scenarios are visible to admin
        scenarios = list(mongo.db.admin.find({
            '_id': {'$in': object_ids},
            'visible_to_admin': True
        }))

        if not scenarios:
            return jsonify({"error": "Scenarios not found or not accessible"}), 404

        # Update scenarios to remove visibility
        result = mongo.db.admin.update_many(
            {'_id': {'$in': object_ids}},
            {
                '$set': {
                    'visible_to_users': False
                },
                '$unset': {
                    'user_approval_date': '',
                    'sent_by': ''
                }
            }
        )

        # Delete related notifications
        mongo.db.notifications.delete_many({
            'scenario_id': {'$in': [str(id) for id in object_ids]}
        })

        return jsonify({
            "success": True,
            "message": f"Successfully removed {len(object_ids)} scenarios",
            "modified_count": result.modified_count
        }), 200

    except Exception as e:
        print(f"Error in batch delete: {e}")
        return jsonify({"error": "Failed to delete scenarios"}), 500

@app.route('/superadmin/toggle_user_visibility', methods=['POST'])
def superadmin_toggle_user_visibility():
    """SuperAdmin endpoint to toggle visibility for users and create notifications"""
    try:
        scenario_ids = request.json.get('ids', [])
        action = request.json.get('action', 'add')
        
        if not scenario_ids:
            return jsonify({"error": "No scenarios specified"}), 400

        object_ids = [ObjectId(id) for id in scenario_ids]
        
        if action == 'add':
            # Get scenario details for notifications
            scenarios = mongo.db.admin.find({'_id': {'$in': object_ids}})
            
            # Create notifications for each scenario but DON'T make visible to users yet
            for scenario in scenarios:
                notification = {
                    'title': 'New Scenario From SuperAdmin',
                    'message': f"SuperAdmin has shared a new scenario: '{scenario.get('scenario', 'Unnamed')}'",
                    'timestamp': datetime.now(),
                    'read': False,
                    'accepted': False,
                    'scenario_id': str(scenario['_id']),
                    'source': 'superadmin'
                }
                mongo.db.notifications.insert_one(notification)
                
                # Update scenario to track notification status
                mongo.db.admin.update_one(
                    {'_id': scenario['_id']},
                    {
                        '$set': {
                            'notification_sent': True,
                            'notification_date': datetime.now()
                        }
                    }
                )
                
            # Note: We're not setting visible_to_users here - that happens on acceptance

            return jsonify({
                "message": "Notifications sent successfully",
                "modified_count": len(scenario_ids)
            }), 200
        else:
            # Handle removal case - this stays the same
            result = mongo.db.admin.update_many(
                {'_id': {'$in': object_ids}},
                {
                    '$set': {
                        'visible_to_users': False
                    },
                    '$unset': {
                        'user_approval_date': '',
                        'sent_by': ''
                    }
                }
            )
            
            # Also remove any pending notifications
            mongo.db.notifications.delete_many({
                'scenario_id': {'$in': [str(id) for id in object_ids]}
            })

            return jsonify({
                "message": f"Successfully removed from user view",
                "modified_count": result.modified_count
            }), 200
            
    except Exception as e:
        print(f"Error toggling user visibility: {e}")
        return jsonify({"error": f"Failed to update scenarios: {str(e)}"}), 500

@app.route('/superadmin/current-user-scenarios', methods=['GET'])
def superadmin_get_user_scenarios():
    """Get scenarios that are currently visible to users (for super admin view)"""
    try:
        scenarios = mongo.db.admin.find({"visible_to_users": True})
        return jsonify([{
            "_id": str(doc['_id']),
            "scenario": doc.get('scenario', ''),
            "approval_date": doc.get('user_approval_date', None),
            "admin_approval_date": doc.get('admin_approval_date', None)
        } for doc in scenarios]), 200
    except Exception as e:
        print(f"Error fetching user scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500
        


@app.route('/accept-scenario', methods=['POST'])
def accept_scenario():
    try:
        data = request.json
        scenario_id = data.get('scenario_id')
        
        print(f"Accepting scenario with ID: {scenario_id}")
        
        if not scenario_id:
            return jsonify({"error": "No scenario ID provided"}), 400
            
        # First verify the scenario exists
        scenario = mongo.db.admin.find_one({'_id': ObjectId(scenario_id)})
        if not scenario:
            print(f"Scenario not found: {scenario_id}")
            return jsonify({"error": f"Scenario not found: {scenario_id}"}), 404

        # Delete the notification instead of just marking it as read/accepted
        notification_result = mongo.db.notifications.delete_one(
            {'scenario_id': scenario_id}
        )
        
        print(f"Notification deletion result: {notification_result.deleted_count}")
        
        # Update scenario visibility
        scenario_result = mongo.db.admin.update_one(
            {'_id': ObjectId(scenario_id)},
            {
                '$set': {
                    'visible_to_users': True,
                    'user_approval_date': datetime.now(),
                }
            }
        )
        
        # Add to accepted scenarios collection
        try:
            result = mongo.db.accepted_scenarios.update_one(
                {'_id': ObjectId(scenario_id)},
                {'$set': {
                    'scenario': scenario.get('scenario'),
                    'prompt': scenario.get('prompt'),
                    'question': scenario.get('question'),
                    'acceptance_date': datetime.now()
                }},
                upsert=True
            )
        except Exception as e:
            print(f"Error updating accepted_scenarios: {e}")
        
        return jsonify({
            "success": True,
            "message": "Scenario accepted successfully",
            "debug_info": {
                "notification_deleted": notification_result.deleted_count > 0,
                "scenario_updated": scenario_result.modified_count > 0,
                "scenario_id": scenario_id
            }
        })
        
    except Exception as e:
        print(f"Error accepting scenario: {str(e)}")
        return jsonify({
            "error": str(e),
            "message": "Failed to accept scenario"
        }), 500
        
@app.route('/accepted-scenarios')
def get_accepted_scenarios():
    try:
        scenarios = mongo.db.admin.find({
            "visible_to_users": True  # Only get scenarios that have been accepted
        }).sort('user_approval_date', -1)
        
        return jsonify([{
            "_id": str(scenario['_id']),
            "scenario": scenario.get('scenario'),
            "prompt": scenario.get('prompt'),
            "question": scenario.get('question'),
            "acceptance_date": scenario.get('user_approval_date')
        } for scenario in scenarios])
    except Exception as e:
        print(f"Error fetching accepted scenarios: {e}")
        return jsonify({"error": str(e)}), 500
    
    
    
    
@app.route('/superadmin/current-admin-scenarios', methods=['GET'])
def superadmin_get_admin_scenarios():
    """Get scenarios that are currently visible to admin"""
    try:
        scenarios = mongo.db.admin.find({"visible_to_admin": True})
        return jsonify([{
            "_id": str(doc['_id']),
            "scenario": doc.get('scenario', ''),
            "approval_date": doc.get('admin_approval_date', None),
            "user_visible": doc.get('visible_to_users', False)
        } for doc in scenarios]), 200
    except Exception as e:
        print(f"Error fetching admin scenarios: {e}")
        return jsonify({"error": "Failed to fetch scenarios"}), 500
    #........................................ report.......................
# @app.route('/analyze-conversation', methods=['POST'])
def analyze_conversation_with_gemini(conversation):
    try:
        # Create analysis prompt
        analysis_prompt = f"""
        Analyze the conversation between the user and assistant. Focus on:
        1. Grammar and Language Usage (Score out of 10)
        2. Product Knowledge & Negotiation Skills (Score out of 10)
        3. Confidence Level (Score out of 10)

        Conversation:
        {conversation}

        Provide the scores in JSON format:
        {{
            "Role play Grammar Score": "<score>",
            "Product Knowledge & Negotiation Skills Score": "<score>",
            "Confidence Score": "<score>"
        }}
        """

        # Get response from Gemini
        response = model.generate_content(analysis_prompt)
        
        # Extract JSON from response
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL)
        if not json_str:
            raise ValueError("No JSON found in response")
        
        analysis_data = json.loads(json_str.group())
        return analysis_data

    except Exception as e:
        print(f"Error in Gemini analysis: {str(e)}")
        raise e    

@app.route('/report')
def report():
    try:
        # First check if the file exists
        if not os.path.exists('analysis_report.json'):
            print("Error: analysis_report.json file not found")
            return render_template('report.html', 
                                error="No analysis report found. Please complete a conversation first.")

        # Try to read the file
        try:
            with open('analysis_report.json', 'r', encoding='utf-8') as file:
                analysis_data = json.load(file)
                print("Successfully loaded analysis data:", analysis_data)
        except json.JSONDecodeError as json_err:
            print(f"Error decoding JSON: {str(json_err)}")
            return render_template('report.html', 
                                error="Invalid analysis data format")
        except Exception as file_err:
            print(f"Error reading file: {str(file_err)}")
            return render_template('report.html', 
                                error=f"Error reading analysis data: {str(file_err)}")

        # Check if analysis_data has the expected structure
        required_keys = [
            "Role play Grammar Score",
            "Product Knowledge & Negotiation Skills Score",
            "Confidence Score"
        ]
        
        missing_keys = [key for key in required_keys if key not in analysis_data]
        if missing_keys:
            print(f"Missing required keys in analysis data: {missing_keys}")
            return render_template('report.html', 
                                error=f"Incomplete analysis data: missing {', '.join(missing_keys)}")

        return render_template('report.html', analysis=analysis_data)
    
    except Exception as e:
        print(f"Unexpected error in report route: {str(e)}")
        return render_template('report.html', 
                            error=f"An unexpected error occurred: {str(e)}")# def analyze_conversation():
#     try:
#         data = request.json
#         print("Received Data:", data)
#         conversation = data.get('conversation', '')
#         print("Conversation Content:", conversation[:100])  # First 100 chars
        
#         if not conversation:
#             return jsonify({
#                 'error': 'Empty conversation data'
#             }), 400
        
#         # Configure Gemini API
#         genai.configure(api_key='AIzaSyCPSOGZfzQlvPyfFKILzy1POXL9gYD9py0')
#         model = genai.GenerativeModel('gemini-pro')

#         # Create analysis prompt
#         analysis_prompt = """
#         Analyze this customer service conversation and provide a detailed assessment. 
#         Structure your response as a JSON object with the following format:

#         {
#             "overallScore": <0-100>,
#             "communicationSkills": {
#                 "overall": <0-100>,
#                 "clarity": <0-100>,
#                 "listening": <0-100>,
#                 "empathy": <0-100>
#             },
#             "negotiationSkills": {
#                 "overall": <0-100>,
#                 "problemSolving": <0-100>,
#                 "flexibility": <0-100>,
#                 "conflictResolution": <0-100>
#             },
#             "conversationStructure": {
#                 "overall": <0-100>,
#                 "opening": <0-100>,
#                 "development": <0-100>,
#                 "resolution": <0-100>,
#                 "closing": <0-100>
#             },
#             "approachTechnique": {
#                 "overall": <0-100>,
#                 "professionalism": <0-100>,
#                 "engagement": <0-100>,
#                 "situationHandling": <0-100>
#             },
#             "responseQuality": {
#                 "overall": <0-100>,
#                 "accuracy": <0-100>,
#                 "completeness": <0-100>,
#                 "timing": <0-100>
#             },
#             "customerInteraction": {
#                 "overall": <0-100>,
#                 "satisfaction": <0-100>,
#                 "issueResolution": <0-100>,
#                 "relationshipBuilding": <0-100>
#             },
#             "detailedAnalysis": [
#                 {
#                     "title": <string>,
#                     "description": <string>,
#                     "score": <0-100>
#                 }
#             ],
#             "recommendations": [
#                 {
#                     "title": <string>,
#                     "description": <string>,
#                     "type": "strength" or "improvement",
#                     "priority": "high" or "medium" or "low"
#                 }
#             ],
#             "keyInsights": [<string>]
#         }

#         Focus on:
#         1. Communication quality and effectiveness
#         2. Professional approach and customer handling
#         3. Problem-solving and negotiation skills
#         4. Conversation structure and flow
#         5. Response appropriateness and completeness
#         6. Overall interaction quality

#         Provide specific examples from the conversation to support your analysis.
#         Remember to maintain strict JSON format in your response.

#         Conversation to analyze: 
#         """ + conversation

#         # Get response from Gemini
#         response = model.generate_content(analysis_prompt)
        
#         # Extract JSON from response
#         json_str = re.search(r'\{.*\}', response.text, re.DOTALL)
#         if not json_str:
#             raise ValueError("No JSON found in response")
            
#         analysis_data = json.loads(json_str.group())

#         # Store analysis in database
#         analysis_record = {
#             'conversation': conversation,
#             'analysis': analysis_data,
#             'timestamp': datetime.utcnow(),
#             'conversation_id': str(request.args.get('conversation_id', '')),
#         }
        
#         mongo.db.conversation_analyses.insert_one(analysis_record)

#         return jsonify(analysis_data)

#     except Exception as e:
#         print(f"Error in conversation analysis: {str(e)}")
#         return jsonify({
#             'error': 'Analysis failed',
#             'message': str(e)
#         }), 500
    

@app.route('/save_chat_history', methods=['POST'])
def save_chat_history():
    try:
        # Get chat history from request
        data = request.get_json()
        if not data or 'chatHistory' not in data:
            return jsonify({
                'error': 'No chat history provided'
            }), 400

        chat_history = data['chatHistory']
        
        # Clean and format the chat history
        cleaned_history = (chat_history.replace('<br>', '\n') .replace('<br/>', '\n')
                         .strip())
        
        # Format into clear user/assistant exchanges
        formatted_lines = []
        current_speaker = None
        current_message = []
        
        for line in cleaned_history.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('User:'):
                if current_speaker and current_message:
                    formatted_lines.append(f"{current_speaker}: {' '.join(current_message)}")
                current_speaker = 'User'
                current_message = [line[5:].strip()]
            elif line.startswith('Assistant:'):
                if current_speaker and current_message:
                    formatted_lines.append(f"{current_speaker}: {' '.join(current_message)}")
                current_speaker = 'Assistant'
                current_message = [line[10:].strip()]
            else:
                current_message.append(line)
                
        if current_speaker and current_message:
            formatted_lines.append(f"{current_speaker}: {' '.join(current_message)}")
            
        final_history = '\n'.join(formatted_lines)
        
        # Save formatted history
        print("Saving chat history...")
        with open('chat_history.txt', 'w', encoding='utf-8') as f:
            f.write(final_history)
            
        print("Analyzing conversation...")
        try:
            analysis_results = analyze_conversation_with_gemini(final_history)
            print("Analysis results:", analysis_results)
            
            # Save analysis results
            with open('analysis_report.json', 'w', encoding='utf-8') as f:
                json.dump(analysis_results, f, indent=4)
            
            return jsonify({
                "message": "Chat history and analysis saved successfully!",
                "analysis": analysis_results
            }), 200
            
        except Exception as analysis_error:
            print(f"Analysis error: {str(analysis_error)}")
            return jsonify({
                'error': 'Analysis failed',
                'message': str(analysis_error)
            }), 500

    except Exception as e:
        print(f"Error in save_chat_history: {str(e)}")
        return jsonify({
            'error': 'Failed to save chat history',
            'message': str(e)
        }), 500
        
@app.route('/analysis-history')
def get_analysis_history():
    try:
        # Get all analyses, sorted by timestamp
        analyses = mongo.db.conversation_analyses.find(
            {},
            {'conversation': 0}  # Exclude full conversation text to reduce payload
        ).sort('timestamp', -1)
        
        return jsonify([{
            'id': str(analysis['_id']),
            'timestamp': analysis['timestamp'],
            'overall_score': analysis['analysis']['overallScore'],
            'conversation_id': analysis.get('conversation_id', '')
        } for analysis in analyses])

    except Exception as e:
        print(f"Error retrieving analysis history: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve analysis history',
            'message': str(e)
        }), 500

# Add route to get specific analysis by ID
@app.route('/analysis/<analysis_id>')
def get_analysis(analysis_id):
    try:
        analysis = mongo.db.conversation_analyses.find_one({
            '_id': ObjectId(analysis_id)
        })
        
        if not analysis:
            return jsonify({
                'error': 'Analysis not found'
            }), 404

        return jsonify({
            'id': str(analysis['_id']),
            'timestamp': analysis['timestamp'],
            'analysis': analysis['analysis'],
            'conversation_id': analysis.get('conversation_id', '')
        })

    except Exception as e:
        print(f"Error retrieving analysis: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve analysis',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
    
    
