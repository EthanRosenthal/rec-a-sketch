from flask import Flask

from .config import configure_app
from .helpers import get_instance_folder_path


app = Flask(__name__,
            instance_path=get_instance_folder_path(),
            instance_relative_config=True,
            template_folder='templates')

configure_app(app)

from app import views