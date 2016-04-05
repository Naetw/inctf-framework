#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Standard library imports
import json

# Imports from third party packages
import yaml
from flask import Flask, render_template
from flask_httpauth import HTTPBasicAuth
import redis

app = Flask(__name__)
auth = HTTPBasicAuth()
config_file = "config.yml"
fh = open(config_file)
config = yaml.load(fh.read())
fh.close()
redis_client = redis.StrictRedis(host='localhost', port='6379', db=0)

team_ids = {}
for team in config['teams']:
    team_ids[config['teams'][team]['name']] = team


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


@app.route('/scores')
def get_scores():
    return redis_client.get('ctf_scores')


@app.route('/services')
@auth.login_required
def get_services():
    return redis_client.get('ctf_services')


@app.route('/services_status')
@auth.login_required
def get_services_status():
    status = json.loads(redis_client.get('ctf_services_status'))
    result = {}
    current_team_id = team_ids[auth.username()]
    for state in status:
        if state['team_id'] == current_team_id:
            print "name: %s, team_id: %d" % (auth.username(), current_team_id)
            for entry in state['services']:
                result[entry['service_id']] = entry['state']

            break

    return json.dumps(result)


if __name__ == "__main__":
    app.run('0.0.0.0', 8000)
