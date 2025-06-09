from flask import Blueprint, render_template

camera_bp = Blueprint('camera', __name__, url_prefix='/camera')

@camera_bp.route('/')
def camera_view():
    return render_template('camera.html')