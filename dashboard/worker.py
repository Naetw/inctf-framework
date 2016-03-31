#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Standard library imports
import json

# Imports from third party packages
import redis
import requests
import yaml


REFRESH_INTERVAL = 1  # seconds


class RedisUpdater(object):
    def __init__(self, api_url, secret):
        self.api_url = api_url
        self.params = {"secret": secret}
        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

    def ctf_services(self):
        url = '/'.join([self.api_url, "getlatestflagids"])
        flag_ids = requests.get(url, self.params).json()["flag_ids"]
        services = {}
        for team in flag_ids:
            team_id = int(team)
            for service in flag_ids[team]:
                service_id = int(service)
                flag_id_info = {"flag_id": flag_ids[team][service],
                                "team_id": team_id}

                if service_id not in services:
                    services[service_id] = {}

                if "flag_id" not in services[service_id]:
                    services[service_id]["flag_id"] = {}

                if "flag_ids" not in services[service_id]["flag_id"]:
                    services[service_id]["flag_id"]["flag_ids"] = []

                services[service_id]["flag_id"]["flag_ids"].append(flag_id_info)

        url = '/'.join([self.api_url, 'getgameinfo'])
        services_info = requests.get(url, params=self.params).json()['services']
        for service_info in services_info:
            service_id = service_info['service_id']
            services[service_id]['description'] = service_info['description']
            services[service_id]['port'] = service_info['internal_port']
            services[service_id]['name'] = service_info['service_name']
            services[service_id]['flag_id']['description'] = \
                service_info['flag_id_description']
            services[service_id]['flag_id']['flag_ids'].sort(
                key=lambda x: x['team_id'])

        self.store_redis('ctf_services', json.dumps(services))
        return

    def ctf_services_status(self):
        url = '/'.join([self.api_url, "getservicesstate"])
        r = requests.get(url, params=self.params)
        self.store_redis('ctf_services_status', json.dumps(r.json()["teams"]))
        return

    def ctf_teams(self):
        url = '/'.join([self.api_url, "getgameinfo"])
        r = requests.get(url, params=self.params)
        teams_data = r.json()["teams"]
        teams = {}
        for team_data in teams_data:
            team_id = int(team_data["team_id"])
            teams[team_id] = {"team_id": team_id,
                              "team_name": team_data["team_name"]}

        self.store_redis('ctf_teams', json.dumps(teams))
        return

    def ctf_scores(self):
        url = '/'.join([self.api_url, "getgameinfo"])
        r = requests.get(url, params=self.params)
        teams_data = r.json()["teams"]
        teams_names = {}
        for team_data in teams_data:
            teams_names[team_data["team_id"]] = team_data["team_name"]

        url = '/'.join([self.api_url, "scores"])
        r = requests.get(url, params=self.params)
        scores_data = r.json()["scores"]
        scores = {}
        for team in scores_data:
            team_id = int(team)
            scores[teams_names[team_id]] = scores_data[team]

        self.store_redis('ctf_scores', json.dumps(scores))

    def store_redis(self, key, value):
        self.redis_client.set(key, value)
        return


def main():
    config_file = "config.yml"
    fh = open(config_file)
    config = yaml.load(fh.read())
    fh.close()
    redis_updater = RedisUpdater(config["api_base_url"], config["api_secret"])
    methods_to_run = [member for member in dir(redis_updater) if
                      member.startswith("ctf_") and '__func__' in dir(member)]
    for method in methods_to_run:
        getattr(redis_updater, method)()


if __name__ == "__main__":
    main()
