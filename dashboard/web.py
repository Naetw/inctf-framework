#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Standard library imports
import json

# Imports from third party packages
import yaml
from flask import Flask, render_template
from flask_httpauth import HTTPBasicAuth

app = Flask(__name__)
auth = HTTPBasicAuth()
config_file = "config.yml"
fh = open(config_file)
config = yaml.load(fh.read())
fh.close()


@auth.get_password
def get_pass(username):
    for team in config['teams']:
        if config['teams'][team]['name'] == username:
            return config['teams'][team]['hashed_password']

    return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/config')
@auth.login_required
def get_config():
    return json.dumps({'ctf_name': config['name'], 'team_name': auth.username()})


if __name__ == "__main__":
    app.run('127.0.0.1', 8000)
