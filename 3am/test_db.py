from app import create_app, db
from app.models import User, ChatRoom, ChatMessage
from app.routes.chat import handle_message

app = create_app()

with app.app_context():
    # Ensure there's a user and a room
    user = User.query.first()
    if not user:
        user = User(username="testuser", email="test@test.com")
        user.set_password("pass")
        db.session.add(user)
        db.session.commit()
    
    room = ChatRoom.query.first()
    if not room:
        room = ChatRoom(name="Test Room", topic="test", description="Test room")
        db.session.add(room)
        db.session.commit()

    print(f"User ID: {user.id}, Room ID: {room.id}")

    # To test handle_message, we would need request context and current_user to be set which is hard in SocketIO
    # But wait, we can just test if the DB operation works!
    try:
        msg_obj = ChatMessage(
            room_id=room.id,
            user_id=user.id,
            message="Test message",
            is_anonymous=user.is_anonymous_mode
        )
        db.session.add(msg_obj)
        db.session.commit()
        print("Success adding to database!!!")
    except Exception as e:
        print(f"Error adding to db: {e}")
