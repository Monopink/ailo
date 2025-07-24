from .contact import ContactRepository
from .profile import ProfileRepository
from .bot_template import TemplateRepository
from .bot import BotRepository

# Create global repository instances
contact = ContactRepository()
profile = ProfileRepository()
bot = BotRepository()
bot_template = TemplateRepository()
# TODO Phase 2: Uncomment when bot_repository is implemented
# bot_repository = BotRepository()
# TODO Phase 3: Uncomment when user_repository is implemented
# user_repository = UserRepository()

__all__ = [
    "ContactRepository",
    "ProfileRepository",
    "TemplateRepository",
    "BotRepository",
    "contact",
    "profile",
    "bot_template",
    "bot",
]
