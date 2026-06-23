from .config import config

def get_location_message() -> str:
    """Returns a formatted string with company location and contact details."""
    message = (
        "Here is our location:\n\n"
        "📍 4th Floor, Zimpost Building, Head Office, Harare Main (Inez Terrace & George Silundika Ave), Harare, Zimbabwe.\n\n"
        "Once you arrive, feel free to:\n"
        "📞 Call us at 0786497967 or 0772802438, OR\n"
        "🚶‍♂️ Walk straight into the reception and ask for help. \n\n"
        "We look forward to seeing you!"
    )
    return message
