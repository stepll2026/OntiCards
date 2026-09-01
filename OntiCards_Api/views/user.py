#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from flask import (
    Blueprint, g, render_template, current_app
)

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/login', methods=['POST', 'GET'])
def index():
    return render_template('index.html')
