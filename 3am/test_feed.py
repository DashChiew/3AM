from app import create_app
from app.routes.feed import is_judgmental_comment

app = create_app()

with app.app_context():
    print("Testing judgmental comment:", is_judgmental_comment("You are so lazy"))
    print("Testing supportive comment:", is_judgmental_comment("I am here for you"))
