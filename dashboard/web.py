#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Standard library imports
import json

# Imports from third party packages
from flask import Flask, jsonify, render_template, request
from flask_httpauth import HTTPBasicAuth
import redis
import requests

app = Flask(__name__)
auth = HTTPBasicAuth()
config_file = "config.json"
fh = open(config_file)
config = json.load(fh)
fh.close()
redis_client = redis.StrictRedis(host='localhost', port='6379', db=0)

team_ids = {}
for team in config['teams']:
    team_ids[config['teams'][team]['name']] = int(team)


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


@app.route('/updatedcontainers')
@auth.login_required
def get_containers_list():
    containers_list = json.loads(redis_client.get('ctf_containers_changed'))
    team = auth.username()
    if team in containers_list:
        return json.dumps(containers_list[auth.username()])
    else:
        return json.dumps([])


@app.route('/exploitlogs')
@auth.login_required
def get_exploit_logs():
    logs = json.loads(redis_client.get('ctf_exploits'))
    team = auth.username()
    if team in logs:
        return json.dumps(logs[auth.username()])
    else:
        return json.dumps([])


@app.route('/flag', methods=['POST'])
@auth.login_required
def submit_flag():
    post_data = json.loads(request.get_data())
    flag = post_data["flag"]
    team = auth.username()
    params = {"secret": config["api_secret"]}
    url = "%s/submitflag/%d/%s" % (config["api_base_url"], team_ids[team],
                                   flag)
    r = requests.get(url, params=params)
    return jsonify(r.json())


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
            for entry in state['services']:
                result[entry['service_id']] = entry['state']

            break

    return json.dumps(result)


@app.route('/tick_change_time')
def get_tick_duration():
    return redis_client.get('ctf_tick_change_time')


if __name__ == "__main__":
    app.run('0.0.0.0', 9000)
