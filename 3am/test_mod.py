from app import create_app
from app.routes.feed import moderate_content

app = create_app()

with app.app_context():
    print("Test 1 (Safe message):", moderate_content("I'm feeling really anxious tonight."))
    print("Test 2 (Address):", moderate_content("My home address is 123 Main St, Apartment 4B."))
    print("Test 3 (Judgmental):", moderate_content("You are just being lazy and selfish."))
