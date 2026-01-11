from app.shared.constants.session_constants import is_valid_athlete

# Test cases
print(f"Daniela gonzalez (Exact): {is_valid_athlete('Daniela gonzalez')}")
print(f"Daniela Gonzalez (Title): {is_valid_athlete('Daniela Gonzalez')}")
print(f"LUIS ANGEL (Upper): {is_valid_athlete('LUIS ANGEL')}")
print(f"Invalid Name: {is_valid_athlete('Invalid Name')}")
